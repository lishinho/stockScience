import pandas as pd
import pandas_ta as ta

"""指标计算模块"""
class Indicators:
    @staticmethod
    def calculate_indicators(df):
        """计算技术指标：均线、MACD、RSI、BOLL、成交量"""
        # 均线
        df['ma5'] = df.ta.sma(length=5)
        df['ma20'] = df.ta.sma(length=20)

        # MACD
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)

        # RSI
        df['rsi'] = df.ta.rsi(length=14)

        # BOLL
        boll = df.ta.bbands(length=20)
        df = pd.concat([df, boll], axis=1)

        # 成交量指标
        df['volume_ma3'] = df['volume'].rolling(window=3).mean()
        df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1

        # 列重命名
        return df.rename(columns={
            'MACD_12_26_9': 'macd',
            'MACDs_12_26_9': 'macd_signal',
            'MACDh_12_26_9': 'macd_hist',
            'BBL_20_2.0': 'boll_lower',
            'BBM_20_2.0': 'boll_mid',
            'BBU_20_2.0': 'boll_upper'
        })