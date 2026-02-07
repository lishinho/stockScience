import pandas as pd
import pandas_ta as ta
import akshare as ak
import numpy as np
from datetime import datetime, timedelta
from data_resilient import DataResilient
from cache_manager import CacheManager

# ========== 数据获取模块 ==========
def fetch_stock_data(symbol, start_date, end_date):
    """通过AKShare获取股票历史数据（日线）- 带缓存和重试"""
    return DataResilient.fetch_stock_data(symbol, start_date, end_date, use_cache=True)

# ========== 指标计算模块（使用 pandas_ta）==========
def calculate_indicators(df):
    """计算技术指标：均线、MACD、RSI、BOLL、成交量"""
    # 均线 (5日, 20日)
    df['ma5'] = df.ta.sma(length=5)
    df['ma20'] = df.ta.sma(length=20)
    
    # MACD (默认参数：fast=12, slow=26, signal=9)
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    
    # RSI (14日)
    df['rsi'] = df.ta.rsi(length=14)
    
    # BOLL (20日)
    boll = df.ta.bbands(length=20)
    df = pd.concat([df, boll], axis=1)
    
    # 成交量变化率（3日平均）
    df['volume_ma3'] = df['volume'].rolling(window=3).mean()
    df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1
    
    # 清理列名
    df.rename(columns={
        'MACD_12_26_9': 'macd',
        'MACDs_12_26_9': 'macd_signal',
        'MACDh_12_26_9': 'macd_hist',
        'BBL_20_2.0': 'boll_lower',
        'BBM_20_2.0': 'boll_mid',
        'BBU_20_2.0': 'boll_upper'
    }, inplace=True)
    
    return df

# ========== 信号生成模块 ==========
def generate_signals(df):
    """根据策略生成买卖信号"""
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0  # 0: 无信号, 1: 买入, -1: 卖出
    
    # 单独存储每个买入条件
    buy_conditions = [
        (df['ma5'] > df['ma20']),  # 条件1: 均线金叉
        (df['macd'] > df['macd_signal']),  # 条件2: MACD金叉
        (df['rsi'] < 30),  # 条件3: RSI超卖
        (df['close'] < df['boll_lower']),  # 条件4: 股价触及BOLL下轨
        (df['volume_pct_change'] > 0.2)  # 条件5: 成交量放大20%
    ]

    # 计算满足条件数量
    satisfied_counts = sum(cond.astype(int) for cond in buy_conditions)
    
    # 新买入条件：至少满足2个条件
    buy_condition = satisfied_counts >= 2
    
    # 卖出条件（任一条件触发）
    sell_condition = (
        (df['macd'] < df['macd_signal']) |  # MACD死叉
        (df['rsi'] > 70) |  # RSI超买
        (df['close'] > df['boll_upper'])  # BOLL触及上轨
    )
    
    
    signals.loc[buy_condition, 'signal'] = 1
    signals.loc[sell_condition, 'signal'] = -1
    return signals

# ========== 回测模块 ==========
def backtest_strategy(df, signals):
    """模拟交易回测"""
    df['position'] = signals['signal'].shift(1)  # 次日开盘执行
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['position'] * df['returns']
    df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
    return df

# ========== 数据获取模块 ==========
def get_hs300_symbols():
    """获取沪深300成分股代码"""
    return DataResilient.get_hs300_symbols(use_cache=True)

# ========== 修改主程序 ==========
if __name__ == "__main__":
    CacheManager.initialize()
    
    symbols = get_hs300_symbols()
    if not symbols:
        raise ValueError("无法获取沪深300成分股数据")
    
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    stock_code_name_df = DataResilient.get_stock_info(use_cache=True)
    code_name_dict = dict(zip(stock_code_name_df['code'], stock_code_name_df['name'])) if not stock_code_name_df.empty else {}

    results = []  # 存储所有股票结果
    
    for symbol in symbols:
        # 提取纯数字代码用于名称查询
        base_symbol = symbol.split('.')[0]
        stock_name = code_name_dict.get(base_symbol, "")
        
        try:
            df = fetch_stock_data(base_symbol, start_date, end_date)
            if df is None or df.empty:
                continue
                
            df = calculate_indicators(df)
            signals = generate_signals(df)
            df = backtest_strategy(df, signals)
            
            # 只记录有买入信号的
            latest_signal = signals.iloc[-1]['signal']
            if latest_signal == 1:
                # 获取最新日期满足的买入条件
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

    # 按累计收益率排序
    sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)
    
    # 格式化输出
    print("\n=== 买入信号股票推荐 (按累计收益率降序) ===")
    print(f"{'名称':<20}{'代码':<15}{'最新日期':<12}{'股价':<8}{'收益率':<10}{'判定依据'}")

    # 正确的输出循环
    for item in sorted_results:
        print(f"{item['name'][:18]:<20}{item['symbol']:<15}{item['date']:<12}"
              f"{item['latest_price']:>6.2f}{item['return']:>8.2%}  {item['criteria']}")