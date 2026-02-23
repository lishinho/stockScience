import pandas as pd
import numpy as np

class IndicatorsCalculator:
    @staticmethod
    def calculate_indicators(df):
        """计算技术指标：均线、MACD、RSI、BOLL、成交量"""
        if df is None or df.empty:
            return df
        
        df = df.copy()
        
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['boll_mid'] = df['close'].rolling(20).mean()
        df['boll_std'] = df['close'].rolling(20).std()
        df['boll_upper'] = df['boll_mid'] + 2 * df['boll_std']
        df['boll_lower'] = df['boll_mid'] - 2 * df['boll_std']
        
        df['volume_ma3'] = df['volume'].rolling(3).mean()
        df['volume_pct_change'] = (df['volume'] / df['volume_ma3'].shift(1)) - 1
        
        return df.dropna()