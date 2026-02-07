import argparse
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from data import DataFetcher
from indicators import IndicatorsCalculator
from signals import SignalGenerator
from backtest import BacktestStrategy
from data import DataCache
import akshare as ak
from threading import Lock
import numpy as np

print_lock = Lock()

"""主执行模块（轻量级改进版）"""
class MainExecutor:
    @staticmethod
    def run(symbols, start_date, end_date):
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for symbol in symbols:
                future = executor.submit(MainExecutor.process_symbol, symbol, start_date, end_date)
                futures.append(future)
            
            completed = 0
            for future in futures:
                try:
                    future.result()
                    completed += 1
                    if completed % 5 == 0:
                        print(f"进度: {completed}/{len(symbols)} ({completed/len(symbols)*100:.1f}%)")
                except Exception as e:
                    pass

    @staticmethod
    def process_symbol(symbol, start_date, end_date):
        try:
            stock_name = DataCache.stock_names.get(symbol, "")
            df = DataFetcher.fetch_stock_data(symbol, start_date, end_date)
            df = IndicatorsCalculator.calculate_indicators(df)
            signals = SignalGenerator.generate_signals(df)
            df = BacktestStrategy.backtest(df, signals)
                
            latest_signal = signals.iloc[-1]['signal']
            latest_date = signals.index[-1].strftime('%Y-%m-%d')
            latest_price = df['close'].iloc[-1]
                
            action = "持有"
            if latest_signal == 1:
                action = "★★★ 买入 ★★★"
            elif latest_signal == -1:
                action = "▼▼▼ 卖出 ▼▼▼"
                
            latest_score = signals.iloc[-1]
            buy_threshold, sell_threshold = SignalGenerator.dynamic_threshold(df)
                
            output = [
                "\n" + "="*40,
                f"股票名称: {stock_name}({symbol})",
                f"数据期间: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                f"\n【{latest_date} 操作建议】{action}",
                f"当前价格: {latest_price:.2f}",
                 "\n【多维评分系统】",
                f"买入评分: {latest_score['buy_score']:.2f}/1.00  (当前阈值: {buy_threshold:.2f})",
                f"卖出压力: {latest_score['sell_pressure']:.2f}/1.00  (当前阈值: {sell_threshold:.2f})",
                "\n买入评分构成：",
                f"MACD动量(0.3): {latest_score['macd_momentum']:.2f}",
                f"BOLL通道(0.2): {latest_score['boll_score']:.2f}",
                f"RSI背离(0.15): {latest_score['rsi_divergence']:.2f}",
                f"量价配合(0.2): {latest_score['volume_score']:.2f}",
                f"宏观因子(0.15): {latest_score['macro_score']:.2f}",
                "\n卖出压力构成：",
                f"趋势衰减(0.1): {latest_score['trend_decay']:.2f}",
                f"超买系数(0.1): {latest_score['overbought']:.2f}", 
                f"资金流出(0.1): {latest_score['capital_outflow']:.2f}",
                f"回撤压力(0.1): {latest_score['drawdown_pressure']:.2f}",
                f"\n累计收益率: {df['cum_returns'].iloc[-1]:.2%}",
                "="*40
            ]
                
            with print_lock:
                print('\n'.join(output))
                
        except Exception as e:
            with print_lock:
                print(f"处理{symbol}时发生错误: {str(e)}")


def parse_quarter(row):
    try:
        quarter_str = str(row['季度'])
        match = re.search(r'(\d+)[年|-]*(?:第)?([1-4])', quarter_str)
        if match:
            year = int(match.group(1))
            quarter_num = int(match.group(2))
            month = (quarter_num - 1) * 3 + 1
            return pd.Timestamp(f'{year}-{month:02d}-01')
        if 'Q' in quarter_str:
            year, q = re.findall(r'(\d+)Q([1-4])', quarter_str)[0]
            month = (int(q) - 1) * 3 + 1
            return pd.Timestamp(f'{year}-{month:02d}-01')
    except Exception as e:
        print(f"季度解析异常：{quarter_str}，错误：{str(e)}")
    today = pd.Timestamp.today()
    return pd.Timestamp(f'{today.year}-{(today.quarter-1)*3+1:02d}-01')


if __name__ == "__main__":
    print("=== Stock Grain Ranking 轻量级改进版 ===")
    print("特点: 进度显示 + 简单统计 + 原始速度\n")
    
    DataCache.initialize()
    
    gdp_df = DataCache.macro_data.get('gdp')
    if gdp_df is None or gdp_df.empty:
        try:
            gdp_df = ak.macro_china_gdp()
            DataCache.macro_data['gdp'] = gdp_df
        except Exception as e:
            print(f"GDP数据加载失败: {str(e)}")
            print("生成GDP测试数据...")
            gdp_df = pd.DataFrame({
                '季度': [f'{year}年第{q}季度' for year in range(2022, 2024) for q in range(1,5)],
                '国内生产总值-绝对值': np.random.uniform(30e12, 40e12, 8),
                '国内生产总值-同比增长': np.random.uniform(4.5, 6.5, 8)
            })
    else:
        gdp_df = pd.DataFrame(gdp_df)

    cpi_df = DataCache.macro_data.get('cpi')
    if cpi_df is None or cpi_df.empty:
        print("生成CPI测试数据...")
        cpi_df = pd.DataFrame({
            '统计时间': pd.date_range(end=pd.Timestamp.now(), periods=12, freq='ME').strftime('%Y年%m月'),
            '全国数值': np.random.uniform(1.5, 3.5, 12)
        })
    else:
        cpi_df = pd.DataFrame(cpi_df)
    
    if '统计时间' in cpi_df.columns:
        cpi_df['日期'] = pd.to_datetime(cpi_df['统计时间'].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月', errors='coerce')
    elif '日期' in cpi_df.columns:
        cpi_df['日期'] = pd.to_datetime(cpi_df['日期'], errors='coerce')
    else:
        cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月', errors='coerce')
    
    cpi_df = cpi_df[cpi_df['日期'] <= pd.Timestamp.now()]
    cpi_df.sort_values('日期', inplace=True)

    if not gdp_df.empty and '季度' in gdp_df.columns:
        gdp_df['季度日期'] = gdp_df.apply(parse_quarter, axis=1)
    else:
        print("警告：GDP数据缺少季度字段，使用默认日期")
        if not gdp_df.empty:
            gdp_df['季度日期'] = pd.Timestamp.now()
        else:
            gdp_df = pd.DataFrame({'季度日期': [pd.Timestamp.now()]})

    print("\n=== 最新宏观数据 ===")
    latest_cpi = cpi_df.iloc[-1]
    try:
        value_columns = [col for col in cpi_df.columns if '数值' in col or '同比' in col or '当月' in col]
        if value_columns:
            cpi_value = latest_cpi.get(value_columns[0], 2.5)
        else:
            cpi_value = latest_cpi.iloc[-2] if len(cpi_df.columns) > 1 else 2.5
        cpi_value = float(cpi_value) if not pd.isnull(cpi_value) else 2.5
        
        if '日期' in cpi_df.columns:
            date_str = latest_cpi['日期'].strftime('%Y年%m月')
        else:
            date_str = cpi_df.iloc[-1, 0]
        print(f"CPI数据日期: {date_str} | 值: {cpi_value:.2f}%")
    except Exception as e:
        print(f"CPI数据处理异常: {str(e)}")
        cpi_value = 2.5

    print("\nGDP增速历史：")
    for _, row in gdp_df.sort_values('季度日期').tail(4).iterrows():
        quarter = row['季度'].replace("年第", "Q").replace("季度", "")
        print(f"{quarter}: 同比{row['国内生产总值-同比增长']:.2f}% 绝对值{row['国内生产总值-绝对值']/1e4:.2f}万亿")

    parser = argparse.ArgumentParser(description='股票策略系统（轻量级改进版）')
    parser.add_argument('-s', '--symbols', required=True, nargs='+', help='股票代码列表（多个代码用空格分隔，例如：600489 601088）')
    parser.add_argument('-b', '--begin', required=True, help='开始日期（格式：YYYYMMDD）')
    parser.add_argument('-e', '--end', default=datetime.now().strftime('%Y%m%d'), help='结束日期（默认当天）')
    args = parser.parse_args()
    
    start_time = datetime.now()
    start_date = datetime.strptime(args.begin, '%Y%m%d')
    end_date = datetime.strptime(args.end, '%Y%m%d')
    
    print(f"分析期间: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print(f"股票数量: {len(args.symbols)}\n")
    
    MainExecutor.run(args.symbols, start_date, end_date)
    
    total_time = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 60)
    print("=== 执行统计 ===")
    print(f"总用时: {total_time:.1f}秒")
    print(f"平均速度: {len(args.symbols)/total_time:.2f} 只/秒")
    print("=" * 60)
