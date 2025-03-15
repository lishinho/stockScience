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
                # 从缓存获取数据
                cpi_df = DataCache.macro_data['cpi']
                
                # 转换为季度和月份用于宏观数据对齐
                quarter = (date.month - 1) // 3 + 1
                target_month = date.strftime("%Y年%m月")
                
                # 1. 获取CPI同比（月度）
                cpi_mask = (cpi_df['日期'] >= date - pd.DateOffset(months=3)) & (cpi_df['日期'] <= date)
                cpi_current = cpi_df[cpi_mask].iloc[-1]['全国-当月'] if any(cpi_mask) else None
                
                if not cpi_current:
                    print(f"CPI数据异常：当前日期{date.strftime('%Y-%m-%d')} 最近可用数据日期{cpi_df['日期'].max().strftime('%Y-%m-%d')}")
                    return 0.10
                
                cpi_score = min(max((float(cpi_current) - 2.5)/2, 0), 1)
                
                fx_df = DataCache.macro_data['fx']
                pmi_df = DataCache.macro_data['pmi']
                gdp_df = DataCache.macro_data['gdp']
                
                # 2. 汇率处理改用更稳定的方式
                cny_rate = fx_df[fx_df['货币对'].str.contains('USD/CNY')].iloc[0]['买报价']
                fx_score = 1 - abs(cny_rate - 6.8)/0.5
                
                # 3. 制造业PMI（月度）
                year_month = date.strftime("%Y年%m月")
                pmi_current = pmi_df[pmi_df['月份'] == year_month]['制造业-指数'].values
                pmi_score = 0.0 if len(pmi_current) == 0 else (float(pmi_current[0]) - 45)/15
                
                # 4. GDP增速（季度）
                quarter_str = f"{date.year}年第{quarter}季度"
                gdp_current = gdp_df[(gdp_df['季度'].str.contains(quarter_str))]['国内生产总值-绝对值'].values
                gdp_growth = 0.0 if len(gdp_current) < 2 else (gdp_current[0]/gdp_current[1] - 1)
                gdp_score = min(max((gdp_growth - 4)/2, 0), 1)
                
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