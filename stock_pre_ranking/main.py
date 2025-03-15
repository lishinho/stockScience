from data import DataFetcher
from indicators import Indicators
from signals import Signals
from backtest import Backtest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak

if __name__ == "__main__":
    symbols = DataFetcher.get_hs300_symbols()
    if not symbols:
        raise ValueError("无法获取沪深300成分股数据")

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    stock_code_name_df = ak.stock_info_a_code_name()
    code_name_dict = dict(zip(stock_code_name_df['code'], stock_code_name_df['name']))

    results = []
    
    for symbol in symbols:
        base_symbol = symbol.split('.')[0]
        stock_name = code_name_dict.get(base_symbol, "")
        
        try:
            df = DataFetcher.fetch_stock_data(base_symbol, start_date, end_date)
            if df is None or df.empty:
                continue
                
            df = Indicators.calculate_indicators(df)
            signals = Signals.generate_signals(df)
            df = Backtest.run(df, signals)
            
            latest_signal = signals.iloc[-1]['signal']
            if latest_signal == 1:
                latest_date = df.index[-1]
                satisfied_conditions = [
                    "均线金叉" if (df.loc[latest_date, 'ma5'] > df.loc[latest_date, 'ma20']) else None,
                    "MACD金叉" if (df.loc[latest_date, 'macd'] > df.loc[latest_date, 'macd_signal']) else None,
                    "RSI超卖" if (df.loc[latest_date, 'rsi'] < 30) else None,
                    "BOLL下轨" if (df.loc[latest_date, 'close'] < df.loc[latest_date, 'boll_lower']) else None,
                    "放量20%" if (df.loc[latest_date, 'volume_pct_change'] > 0.2) else None
                ]
                satisfied_conditions = [x for x in satisfied_conditions if x is not None]
                
                results.append({
                    'symbol': symbol,
                    'name': stock_name,
                    'return': df['cum_returns'].iloc[-1],
                    'latest_price': df['close'].iloc[-1],
                    'date': df.index[-1].strftime('%Y-%m-%d'),
                    'criteria': ' + '.join(satisfied_conditions)
                })
        except Exception as e:
            print(f"处理 {symbol} 时出错: {str(e)}")
            continue

    sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)
    
    print("\n=== 买入信号股票推荐 (按累计收益率降序) ===")
    print(f"{'名称':<20}{'代码':<15}{'最新日期':<12}{'股价':<8}{'收益率':<10}{'判定依据'}")

    for item in sorted_results:
        print(f"{item['name'][:18]:<20}{item['symbol']:<15}{item['date']:<12}"
              f"{item['latest_price']:>6.2f}{item['return']:>8.2%}  {item['criteria']}")