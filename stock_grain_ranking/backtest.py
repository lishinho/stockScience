import pandas as pd
import numpy as np

"""回测模块"""
class BacktestStrategy:
    @staticmethod
    def backtest(df, signals):
        """策略回测和收益计算"""
        df['position'] = signals['signal'].shift(1)
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['position'] * df['returns']
        df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
        return df.dropna()

    @staticmethod
    def generate_report(df, symbol):
        """生成回测报告"""
        latest = df.iloc[-1]
        return {
            'symbol': symbol,
            'final_return': latest['cum_returns'],
            'max_drawdown': (df['cum_returns'].cummax() - df['cum_returns']).max(),
            'sharpe_ratio': df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(252)
        }