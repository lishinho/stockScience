import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from data import DataFetcher
from indicators import IndicatorsCalculator
from signals import SignalGenerator
from backtest import BacktestStrategy
from data import DataCache

"""主执行模块"""
class MainExecutor:
    @staticmethod
    def run(symbols, start_date, end_date):
        with ThreadPoolExecutor(max_workers=8) as executor:
            for symbol in symbols:
                executor.submit(MainExecutor.process_symbol, symbol, start_date, end_date)

    @staticmethod
    def process_symbol(symbol, start_date, end_date):
        # 添加了 start_date 参数，后续逻辑若有需要可使用此参数进行处理
        try:
            df = DataFetcher.get_stock_data(symbol, start_date)
            df = IndicatorsCalculator.calculate_indicators(df)
            signals = SignalGenerator.generate_signals(df)
            if 'signal' in signals.columns:
                df = df.join(signals['signal'])
            else:
                print(f"信号数据中缺少 'signal' 列: {symbol}")
                return
            df = BacktestStrategy.backtest(df, signals)
            
            report = BacktestStrategy.generate_report(df, symbol)
            MainExecutor.print_report(report, df.iloc[-1], df, signals, start_date, end_date)
        except Exception as e:
            print(f"处理{symbol}时发生错误: {str(e)}")

    @staticmethod
    def print_report(report, latest, df, signals, start_date, end_date):
        print("\n" + "="*40)
        print(f"股票名称: {report['symbol']}")
        print(f"数据期间: {start_date} 至 {end_date}")
        
        latest_signal = latest['signal']
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        latest_price = df['close'].iloc[-1]
        
        # 买卖建议
        action = "持有"
        if latest_signal == 1:
            action = "★★★ 买入 ★★★"
        elif latest_signal == -1:
            action = "▼▼▼ 卖出 ▼▼▼"
        
        print(f"\n【{latest_date} 操作建议】{action}")
        print(f"当前价格: {latest_price:.2f}")
        
        # 评分详情
        latest_score = signals.iloc[-1]
        print("\n【多维评分系统】")
        print(f"买入评分: {latest_score['buy_score']:.2f}/1.00  (阈值0.60)")
        if 'sell_pressure' in latest_score:
            print(f"卖出压力: {latest_score['sell_pressure']:.2f}/1.00  (阈值0.50)")
        
        print("\n买入评分构成：")
        print(f"MACD动量(0.3): {latest_score['macd_momentum']:.2f}")
        print(f"BOLL通道(0.2): {latest_score['boll_score']:.2f}")
        print(f"RSI背离(0.15): {latest_score['rsi_divergence']:.2f}")
        print(f"量价配合(0.2): {latest_score['volume_score']:.2f}")
        print(f"宏观因子(0.15): {latest_score['macro_score']:.2f}")
        
        print("\n卖出压力构成：")
        print(f"趋势衰减(0.4): {latest_score['trend_decay']:.2f}")
        print(f"超买系数(0.3): {latest_score['overbought']:.2f}")
        print(f"资金流出(0.2): {latest_score['capital_outflow']:.2f}")
        print(f"黑天鹅指数(0.1): {latest_score['black_swan']:.2f}")
        
        print("\n累计收益率:", f"{df['cum_returns'].iloc[-1]:.2%}")
        print("="*40)


if __name__ == "__main__":
    # 初始化数据缓存
    DataCache.initialize()

    # 新增：处理宏观数据日期格式
    cpi_df = DataCache.macro_data['cpi']
    cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月')
    cpi_df.sort_values('日期', inplace=True)

    # 修改主程序中的GDP日期处理部分
    # 修正后的GDP季度日期处理
    gdp_df = DataCache.macro_data['gdp']

    # 使用更稳健的季度解析方法
    def parse_quarter(row):
        year = int(row['季度'].split('年')[0])
        q = int(row['季度'].split('第')[1][0])
        return pd.Timestamp(year=year, month=q*3-2, day=1)  # 将季度转换为该季第一个月
    
    gdp_df['季度日期'] = gdp_df.apply(parse_quarter, axis=1)

    print("\n=== 最新宏观数据 ===")
    # 打印最新CPI数据
    latest_cpi = cpi_df.iloc[-1]
    print(f"CPI数据日期: {latest_cpi['日期'].strftime('%Y年%m月')} | 值: {latest_cpi.iloc[3]:.2f}%")

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
    
    MainExecutor.run(args.symbols, args.begin, args.end)