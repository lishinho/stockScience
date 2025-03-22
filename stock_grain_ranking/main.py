import argparse
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

"""主执行模块"""
class MainExecutor:
    @staticmethod
    def run(symbols, start_date, end_date):
        with ThreadPoolExecutor(max_workers=8) as executor:
            for symbol in symbols:
                executor.submit(MainExecutor.process_symbol, symbol, start_date, end_date)

    @staticmethod
    def process_symbol(symbol, start_date, end_date):
        try:
            stock_info = ak.stock_info_a_code_name()
            code_name_dict = dict(zip(stock_info['code'], stock_info['name']))
            stock_name = code_name_dict.get(symbol, "")
            df = DataFetcher.fetch_stock_data(symbol, start_date, end_date)
            df = IndicatorsCalculator.calculate_indicators(df)
            signals = SignalGenerator.generate_signals(df)
            df = BacktestStrategy.backtest(df, signals)
                
            latest_signal = signals.iloc[-1]['signal']
            latest_date = signals.index[-1].strftime('%Y-%m-%d')
            latest_price = df['close'].iloc[-1]
                
            # 买卖建议
            action = "持有"
            if latest_signal == 1:
                action = "★★★ 买入 ★★★"
            elif latest_signal == -1:
                action = "▼▼▼ 卖出 ▼▼▼"
                
                # 评分详情
            latest_score = signals.iloc[-1]
                
                # 在生成信号后获取动态阈值
            buy_threshold, sell_threshold = SignalGenerator.dynamic_threshold(df)
                
                # 构建输出内容（原所有print语句改为列表追加）
            output = [
                    "\n" + "="*40,
                    f"股票名称: {stock_name}({symbol})",
                    f"数据期间: {start_date} 至 {end_date}",
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
                # 原子化输出
            with print_lock:
                print('\n'.join(output))
                
        except Exception as e:
            print(f"处理{symbol}时发生错误: {str(e)}")

   

def parse_quarter(row):
    try:
        quarter_str = str(row['季度'])
        # 支持多种季度格式：2023Q4/2023年第4季度/2023-4季度
        match = re.search(r'(\d+)[年|-]*(?:第)?([1-4])', quarter_str)
        if match:
            year = int(match.group(1))
            quarter_num = int(match.group(2))
            month = (quarter_num - 1) * 3 + 1
            return pd.Timestamp(f'{year}-{month:02d}-01')
        # 匹配Q4格式
        if 'Q' in quarter_str:
            year, q = re.findall(r'(\d+)Q([1-4])', quarter_str)[0]
            month = (int(q) - 1) * 3 + 1
            return pd.Timestamp(f'{year}-{month:02d}-01')
    except Exception as e:
        print(f"季度解析异常：{quarter_str}，错误：{str(e)}")
    # 默认返回当前季度首月
    today = pd.Timestamp.today()
    return pd.Timestamp(f'{today.year}-{(today.quarter-1)*3+1:02d}-01')

if __name__ == "__main__":
    # 初始化数据缓存
    DataCache.initialize()

    # 初始化GDP数据
    gdp_df = DataCache.macro_data.get('gdp', pd.DataFrame())
    if gdp_df.empty:
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

    # 新增：处理宏观数据日期格式
    cpi_df = DataCache.macro_data['cpi']
    # 统一使用'统计时间'字段解析日期
    cpi_df['日期'] = pd.to_datetime(cpi_df['统计时间'].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月', errors='coerce')
    # 添加备用解析方案
    if cpi_df['日期'].isnull().any():
        cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月')
    # 新增日期过滤条件
    cpi_df = cpi_df[cpi_df['日期'] <= pd.Timestamp.now()]
    cpi_df.sort_values('日期', inplace=True)

    # 空数据检查与默认数据生成
    if cpi_df.empty or len(cpi_df) < 3:
        print("生成CPI测试数据...")
        cpi_df = pd.DataFrame({
            '统计时间': pd.date_range(end=pd.Timestamp.now(), periods=12, freq='ME'),
            '全国数值': np.random.uniform(1.5, 3.5, 12)
        })

    # 动态日期列匹配
    date_columns = [col for col in cpi_df.columns if '日期' in col or '时间' in col]
    date_col = date_columns[0] if date_columns else cpi_df.columns[0]
    cpi_df['日期'] = pd.to_datetime(cpi_df[date_col])
    
    # 安全创建季度日期列
    if not gdp_df.empty and '季度' in gdp_df.columns:
        gdp_df['季度日期'] = gdp_df.apply(parse_quarter, axis=1)
    else:
        print("警告：GDP数据缺少季度字段，使用默认日期")
        if not gdp_df.empty:
            gdp_df['季度日期'] = pd.Timestamp.now()
        else:
            gdp_df = pd.DataFrame({'季度日期': [pd.Timestamp.now()]})

    print("\n=== 最新宏观数据 ===")
    # 动态匹配CPI数值列
    try:
        # 优先查找包含数值/同比的列
        value_columns = [col for col in cpi_df.columns if '数值' in col or '同比' in col]
        # 安全获取列数据：优先使用找到的列，否则取倒数第二列
        cpi_value = latest_cpi.get(value_columns[0], latest_cpi.iloc[:,-2]) if value_columns else 2.5
        # 最终有效性检查
        cpi_value = float(cpi_value) if not pd.isnull(cpi_value) else 2.5
        
        # 动态日期格式处理
        date_str = latest_cpi['日期'].strftime('%Y年%m月') if '日期' in cpi_df.columns else cpi_df.iloc[-1,0]
        print(f"CPI数据日期: {date_str} | 值: {cpi_value:.2f}%")
    except Exception as e:
        print(f"CPI数据处理异常: {str(e)}")
        print(f"可用字段: {cpi_df.columns.tolist()}")
        cpi_value = 2.5  # 默认值

    # 打印GDP增速数据（最近4个季度）
    print("\nGDP增速历史：")
    for _, row in gdp_df.sort_values('季度日期').tail(4).iterrows():
        quarter = row['季度'].replace("年第", "Q").replace("季度", "")
        # 修正单位转换（原数据单位为亿元，1万亿=10000亿）
        print(f"{quarter}: 同比{row['国内生产总值-同比增长']:.2f}% 绝对值{row['国内生产总值-绝对值']/1e4:.2f}万亿")

    parser = argparse.ArgumentParser(description='股票策略系统')
    parser.add_argument('-s', '--symbols', required=True, nargs='+', help='股票代码列表（多个代码用空格分隔，例如：600489 601088）')
    parser.add_argument('-b', '--begin', required=True, help='开始日期（格式：YYYYMMDD）')
    parser.add_argument('-e', '--end', default=datetime.now().strftime('%Y%m%d'), help='结束日期（默认当天）')
    args = parser.parse_args()
    
    # 转换日期参数为datetime对象
    start_date = datetime.strptime(args.begin, '%Y%m%d')
    end_date = datetime.strptime(args.end, '%Y%m%d')
    
    MainExecutor.run(args.symbols, start_date, end_date)
