import pandas as pd

"""策略回测执行"""
class Backtest:
    @staticmethod
    def run(df, signals):
        """策略回测执行"""
        df['position'] = signals['signal'].shift(1)
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['position'] * df['returns']
        df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
        return df