import pandas as pd
import numpy as np
from data import DataCache

"""信号生成模块"""
class SignalGenerator:
    # ========== 新增市场状态评估函数 ==========
    @staticmethod
    def market_regime(df):
        """评估市场状态 (震荡/趋势)"""
        adx = df.ta.adx(length=14)
        return "trend" if adx['ADX_14'].iloc[-1] > 25 else "range"

    # ========== 修改动态阈值函数 ==========
    @staticmethod
    def dynamic_threshold(df):
        """双阈值动态调整机制"""
        regime = SignalGenerator.market_regime(df)
        volatility = df['close'].pct_change().std() * 100
        
        # 趋势市场参数
        if regime == "trend":
            buy_thresh = 0.62 if volatility > 3 else 0.58
            sell_thresh = 0.12
        # 震荡市场参数
        else:
            buy_thresh = 0.66 if volatility > 3 else 0.63
            sell_thresh = 0.1
        return buy_thresh, sell_thresh

    # ========== 修改信号生成模块 ==========
    @staticmethod
    def generate_signals(df):
        """生成买卖信号（基于多维评分模型）"""
        signals = pd.DataFrame(index=df.index)
        signals['signal'] = 0  # 0: 无信号, 1: 买入, -1: 卖出
        
        # 计算买入评分各分项
        signals['macd_momentum'] = (df['macd'] > df['macd_signal']).astype(int) * 0.3
        signals['boll_score'] = np.where(
            df['close'] < df['boll_lower'],
            1.0,
            np.where(df['close'] > df['boll_mid'],
                     0.5, 
                     0.0)
        ) * 0.2
        signals['rsi_divergence'] = (df['rsi'] < 30).astype(int) * 0.15
        signals['volume_score'] = (df['volume_pct_change'] > 0.2).astype(int) * 0.2
        
        # 修改宏观评分计算
        signals['macro_score'] = df.index.map(lambda x: SignalGenerator.get_macro_score(x))
        
        # 总买入评分
        signals['buy_score'] = signals[['macd_momentum','boll_score','rsi_divergence','volume_score','macro_score']].sum(axis=1)
        
        # 计算卖出压力各分项
        # 趋势衰减（使用均线偏离度和MACD柱状体连续计算）
        ma_decay = (df['ma20'] - df['ma5']) / df['ma20']  # 计算均线偏离百分比
        macd_decay = (df['macd_signal'] - df['macd']) / (df['macd_signal'].abs() + 1e-6)  # MACD负向强度
        signals['trend_decay'] = np.clip((ma_decay * 0.6 + macd_decay * 0.4), 0, 1) * 0.1  # 加权综合
        
        # 超买系数（使用RSI连续值）
        signals['overbought'] = np.clip((df['rsi'] - 60) / (100 - 60), 0, 1) * 0.1  # RSI在60-100区间线性变化
        
        # 资金流出（计算量能萎缩程度）
        vol_ratio = np.clip((-df['volume_pct_change'] - 0.1) / 0.8, 0, 1)  # -10%以下开始计算，-100%时达上限
        signals['capital_outflow'] = vol_ratio * 0.1
        
        # 新增回撤压力系数（原黑天鹅指数部分）
        pct_change = df['close'].pct_change()
        price_drops = (-pct_change).clip(lower=0)
        
        # 新条件：3日移动窗口中有2日下跌，且累计跌幅超过1.5%
        three_day_drop = (pct_change < 0).rolling(3).sum() >= 2
        cumulative_drop = pct_change.rolling(3).sum() < -0.015  # 三日累计跌幅超1.5%
        
        # 优化单日大跌条件：跌幅超2.5%且成交量放大
        volume_spike = df['volume'] > df['volume_ma3'] * 1.2  # 成交量超过3日均量20%
        single_day_drop = (pct_change < -0.025) & volume_spike
        
        # 计算回撤压力系数
        drawdown_ratio = np.clip(price_drops / 0.03, 0, 1)
        signals['drawdown_pressure'] = np.where(
            (three_day_drop & cumulative_drop) | single_day_drop,
            1.0, 
            drawdown_ratio
        ) * 0.1
        
        # 总卖出压力（更新列名）
        signals['sell_pressure'] = signals[['trend_decay','overbought','capital_outflow','drawdown_pressure']].sum(axis=1)
        
        # 生成信号
        # 动态调整买入阈值
        # 修改阈值获取方式（同时获取买卖阈值）
        buy_threshold, sell_threshold = SignalGenerator.dynamic_threshold(df)  
        
        # 修改信号生成条件
        signals['signal'] = np.select(
            [signals['buy_score'] >= buy_threshold, 
             signals['sell_pressure'] >= sell_threshold],  
            [1, -1],
            default=0
        )
        
        return signals.dropna()

    @staticmethod
    def get_macro_score(date):
        try:
            cpi_df = DataCache.macro_data.get('cpi')
            if cpi_df is None or cpi_df.empty:
                return 0.10
            
            cpi_df = pd.DataFrame(cpi_df)
            
            quarter = (date.month - 1) // 3 + 1
            
            if '日期' not in cpi_df.columns:
                return 0.10
            
            cpi_mask = (cpi_df['日期'] >= date - pd.DateOffset(months=3)) & (cpi_df['日期'] <= date)
            
            if not any(cpi_mask):
                return 0.10
            
            cpi_current = cpi_df[cpi_mask].iloc[-1]
            value_columns = [col for col in cpi_df.columns if '数值' in col or '同比' in col or '当月' in col]
            if value_columns:
                cpi_value = cpi_current.get(value_columns[0], 2.5)
            else:
                cpi_value = 2.5
            
            cpi_value = float(cpi_value) if not pd.isnull(cpi_value) else 2.5
            cpi_score = min(max((cpi_value - 2.5)/2, 0), 1)
            
            fx_df = DataCache.macro_data.get('fx', pd.DataFrame())
            pmi_df = DataCache.macro_data.get('pmi', pd.DataFrame())
            gdp_df = DataCache.macro_data.get('gdp', pd.DataFrame())
            
            if fx_df.empty or '货币对' not in fx_df.columns:
                fx_score = 0.5
            else:
                cny_rate = fx_df[fx_df['货币对'].str.contains('USD/CNY', na=False)].iloc[0]['买报价'] if not fx_df[fx_df['货币对'].str.contains('USD/CNY', na=False)].empty else 7.0
                fx_score = 1 - abs(cny_rate - 7)/0.5
            
            if pmi_df.empty or '月份' not in pmi_df.columns:
                pmi_score = 0.5
            else:
                year_month = date.strftime("%Y年%m月")
                pmi_current = pmi_df[pmi_df['月份'] == year_month]['制造业-指数'].values
                pmi_score = 0.0 if len(pmi_current) == 0 else (float(pmi_current[0]) - 45)/15
            
            if gdp_df.empty or '季度' not in gdp_df.columns:
                gdp_score = 0.5
            else:
                gdp_df['年份'] = gdp_df['季度'].str.split('年').str[0].astype(int)
                quarter_str = f"{date.year}年第{quarter}季度"
                gdp_current = gdp_df[(gdp_df['季度'].str.contains(quarter_str, na=False))]['国内生产总值-绝对值'].values
                gdp_growth = 0.0 if len(gdp_current) < 2 else (gdp_current[0]/gdp_current[1] - 1)
                gdp_score = min(max((gdp_growth - 4)/2, 0), 1)
            
            weights = [0.3, 0.3, 0.2, 0.2]
            total_score = (cpi_score*weights[0] + fx_score*weights[1] + \
                          pmi_score*weights[2] + gdp_score*weights[3]) * 0.15
            
            return max(min(total_score, 0.15), 0)
            
        except Exception as e:
            return 0.10