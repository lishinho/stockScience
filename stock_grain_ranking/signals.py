import pandas as pd
import numpy as np
from data import DataCache

"""信号生成模块"""
class SignalGenerator:
    @staticmethod
    def dynamic_threshold(df):
        """根据波动率调整信号阈值"""
        volatility = df['close'].pct_change().std() * 100
        return 0.65 if volatility > 3 else 0.6

    @staticmethod
    def generate_signals(df):
        """生成买卖信号（基于多维评分模型）"""
        signals = pd.DataFrame(index=df.index)
        signals['signal'] = 0
        
        # 计算买入评分各分项
        signals['macd_momentum'] = (df['macd'] > df['macd_signal']).astype(int) * 0.3
        signals['boll_score'] = np.where(
            df['close'] < df['boll_lower'],
            1.0,
            np.where(df['close'] > df['boll_mid'], 0.5, 0.0)
        ) * 0.2
        signals['rsi_divergence'] = (df['rsi'] < 30).astype(int) * 0.15
        signals['volume_score'] = (df['volume_pct_change'] > 0.2).astype(int) * 0.2
        
        # 总买入评分
        buy_threshold = SignalGenerator.dynamic_threshold(df)
        
        # 新增宏观评分计算
        def get_macro_score(date):
            try:
                # 获取当月CPI数据
                cpi_month = date.strftime('%Y-%m')
                cpi_value = DataCache.macro_data['cpi'].set_index('日期').loc[cpi_month].iloc[3]
                
                # 获取最近季度GDP增速
                gdp_data = DataCache.macro_data['gdp']
                latest_gdp = gdp_data[gdp_data['季度日期'] <= date].iloc[-1]['国内生产总值-同比增长']
                
                return (cpi_value * 0.6 + latest_gdp * 0.4) / 100  # 归一化处理
            except:
                return 0.15  # 默认值
        
        signals['macro_score'] = df.index.map(get_macro_score) * 0.15
        
        # 调整买入评分计算公式
        signals['buy_score'] = signals[['macd_momentum','boll_score','rsi_divergence','volume_score','macro_score']].sum(axis=1)
        
        # 调整动态阈值计算逻辑
        buy_threshold = 0.60 + (signals['macro_score'].mean() * 0.05)
        
        # 计算卖出压力各分项
        signals['trend_decay'] = ((df['ma5'] < df['ma20']) | (df['macd'] < df['macd_signal'])).astype(int) * 0.4
        signals['overbought'] = (df['rsi'] > 70).astype(int) * 0.3
        signals['capital_outflow'] = (df['volume_pct_change'] < -0.2).astype(int) * 0.2
        # 添加黑天鹅事件评分
        signals['black_swan'] = np.where(
            (df['volume'] > df['volume'].rolling(20).mean() * 3) &
            (df['close'].pct_change() < -0.05),
            1.0, 0.0
        ) * 0.1

        # 调整卖出压力计算公式
        signals['sell_pressure'] = signals[['trend_decay','overbought','capital_outflow','black_swan']].sum(axis=1)
        
        # 生成信号
        signals['signal'] = np.select(
            [signals['buy_score'] >= buy_threshold, signals[['trend_decay','overbought','capital_outflow']].sum(axis=1) >= 0.5],
            [1, -1],
            default=0
        )
        return signals.dropna()