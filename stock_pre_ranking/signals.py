import pandas as pd

"""交易信号生成"""
class Signals:
    @staticmethod
    def generate_signals(df):
        """根据策略生成买卖信号"""
        signals = pd.DataFrame(index=df.index)
        signals['signal'] = 0

        buy_conditions = [
            (df['ma5'] > df['ma20']),
            (df['macd'] > df['macd_signal']),
            (df['rsi'] < 30),
            (df['close'] < df['boll_lower']),
            (df['volume_pct_change'] > 0.2)
        ]

        satisfied_counts = sum(cond.astype(int) for cond in buy_conditions)
        buy_condition = satisfied_counts >= 2

        sell_condition = (
            (df['macd'] < df['macd_signal']) |
            (df['rsi'] > 70) |
            (df['close'] > df['boll_upper'])
        )

        signals.loc[buy_condition, 'signal'] = 1
        signals.loc[sell_condition, 'signal'] = -1
        return signals