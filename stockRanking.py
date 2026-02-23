import pandas as pd
import pandas_ta as ta
import akshare as ak
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import traceback
import threading
from data_resilient import DataResilient
from cache_manager import CacheManager

print_lock = threading.Lock()

def fetch_stock_data(symbol, start_date, end_date):
    """通过AKShare获取股票历史数据（日线）- 带缓存和重试"""
    return DataResilient.fetch_stock_data(symbol, start_date, end_date, use_cache=True)

# ========== 指标计算模块 ==========
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
    
    df = df.dropna()
    
    return df

# ========== 信号生成模块 ==========
# ========== 新增市场状态评估函数 ==========
def market_regime(df):
    """评估市场状态 (震荡/趋势)"""
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.DataFrame({
            'hl': high - low,
            'hc': abs(high - close.shift(1)),
            'lc': abs(low - close.shift(1))
        }).max(axis=1)
        
        atr = tr.rolling(14).mean()
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        
        return "trend" if adx.iloc[-1] > 25 else "range"
    except:
        return "range"

def dynamic_threshold(df):
    """双阈值动态调整机制"""
    regime = market_regime(df)
    volatility = df['close'].pct_change().std() * 100
    
    if regime == "trend":
        buy_thresh = 0.62 if volatility > 3 else 0.58
        sell_thresh = 0.12
    else:
        buy_thresh = 0.66 if volatility > 3 else 0.63
        sell_thresh = 0.1
    return buy_thresh, sell_thresh

# ========== 修改信号生成模块 ==========
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
    signals['macro_score'] = df.index.map(lambda x: get_macro_score(x))
    
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
    buy_threshold, sell_threshold = dynamic_threshold(df)  
    
    # 修改信号生成条件
    signals['signal'] = np.select(
        [signals['buy_score'] >= buy_threshold, 
         signals['sell_pressure'] >= sell_threshold],  
        [1, -1],
        default=0
    )
    
    return signals.dropna()

def get_macro_score(date):
    """使用缓存的宏观数据"""
    try:
        cpi_df = DataCache.macro_data.get('cpi', pd.DataFrame())
        if cpi_df.empty:
            return 0.10
        
        quarter = (date.month - 1) // 3 + 1
        
        if '日期' not in cpi_df.columns:
            return 0.10
            
        cpi_mask = (cpi_df['日期'] >= date - pd.DateOffset(months=3)) & (cpi_df['日期'] <= date)
        filtered_cpi = cpi_df[cpi_mask]
        
        if filtered_cpi.empty or '全国-当月' not in filtered_cpi.columns:
            return 0.10
        
        cpi_current = filtered_cpi.iloc[-1]['全国-当月']
        if pd.isna(cpi_current):
            return 0.10
            
        cpi_score = min(max((float(cpi_current) - 2.5)/2, 0), 1)
        
        fx_df = DataCache.macro_data.get('fx', pd.DataFrame())
        pmi_df = DataCache.macro_data.get('pmi', pd.DataFrame())
        gdp_df = DataCache.macro_data.get('gdp', pd.DataFrame())
        
        if fx_df.empty or '货币对' not in fx_df.columns:
            fx_score = 0.5
        else:
            usd_cny = fx_df[fx_df['货币对'].str.contains('USD/CNY', na=False)]
            if usd_cny.empty or '买报价' not in usd_cny.columns:
                fx_score = 0.5
            else:
                cny_rate = usd_cny.iloc[0]['买报价']
                if pd.isna(cny_rate):
                    fx_score = 0.5
                else:
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
            quarter_str = f"{date.year}年第{quarter}季度"
            gdp_current = gdp_df[(gdp_df['季度'].str.contains(quarter_str, na=False))]['国内生产总值-绝对值'].values
            gdp_growth = 0.0 if len(gdp_current) < 2 else (gdp_current[0]/gdp_current[1] - 1)
            gdp_score = min(max((gdp_growth - 4)/2, 0), 1)
        
        weights = [0.3, 0.3, 0.2, 0.2]
        total_score = (cpi_score*weights[0] + fx_score*weights[1] + 
                      pmi_score*weights[2] + gdp_score*weights[3]) * 0.15
        
        return max(min(total_score, 0.15), 0)
        
    except Exception as e:
        return 0.10

# ========== 回测模块 ==========
# ========== 新增风控模块 ==========
def risk_management(df):
    """动态风险控制机制"""
    # 计算累计收益回撤
    df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
    df['max_returns'] = df['cum_returns'].cummax()
    df['drawdown'] = (df['cum_returns'] - df['max_returns']) / df['max_returns']
    
    # 当回撤超过10%时暂停交易
    df['position'] = np.where(df['drawdown'] < -0.1, 0, df['position'])
    
    # 连续止损控制（最近3次交易中有2次止损）
    df['loss_flag'] = (df['strategy_returns'] < 0).astype(int)
    df['recent_loss'] = df['loss_flag'].rolling(window=3).sum()
    df['position'] = np.where(df['recent_loss'] >= 2, 0, df['position'])
    
    return df

# ========== 修改回测模块 ==========
def backtest_strategy(df, signals):
    """模拟交易回测"""
    df['position'] = signals['signal'].shift(1)
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['position'] * df['returns']
    df = risk_management(df)  # 加入风控逻辑
    df['cum_returns'] = (1 + df['strategy_returns']).cumprod()
    return df.dropna()

# ========== 新增模块：全局缓存 ==========
class DataCache:
    macro_data = {}
    stock_names = {}

# ========== 修改主程序循环 ==========
from concurrent.futures import ThreadPoolExecutor

if __name__ == "__main__":
    CacheManager.initialize()
    
    print("\n" + "="*60)
    print("  🚀 StockScience 股票分析系统 🚀")
    print("="*60)
    
    print("\n📊 正在初始化数据...")
    
    try:
        stock_info = DataResilient.get_stock_info(use_cache=True)
        DataCache.stock_names = dict(zip(stock_info['code'], stock_info['name'])) if not stock_info.empty else {}
        print(f"✅ 获取股票名称映射: {len(DataCache.stock_names)} 只")
    except Exception as e:
        print(f"⚠️ 获取股票名称失败: {e}")
        DataCache.stock_names = {}
    
    print("\n📊 正在获取宏观数据...")
    try:
        DataCache.macro_data = {
            'cpi': DataResilient.fetch_macro_data('cpi', use_cache=True),
            'fx': DataResilient.fetch_macro_data('fx', use_cache=True),
            'pmi': DataResilient.fetch_macro_data('pmi', use_cache=True),
            'gdp': DataResilient.fetch_macro_data('gdp', use_cache=True)
        }
        print("✅ 宏观数据获取成功")
    except Exception as e:
        print(f"⚠️ 宏观数据获取失败: {e}")
        DataCache.macro_data = {
            'cpi': pd.DataFrame(),
            'fx': pd.DataFrame(),
            'pmi': pd.DataFrame(),
            'gdp': pd.DataFrame()
        }

    if DataCache.macro_data['cpi'].empty:
        print("⚠️ CPI数据获取失败，使用默认值")
        DataCache.macro_data['cpi'] = pd.DataFrame({
            '日期': [datetime.now()],
            '全国-当月': [2.5]
        })

    cpi_df = DataCache.macro_data['cpi']
    if '日期' not in cpi_df.columns:
        cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月', errors='coerce')
    cpi_df.sort_values('日期', inplace=True)
    
    gdp_df = DataCache.macro_data['gdp']
    if not gdp_df.empty and '季度' in gdp_df.columns:
        def parse_quarter(row):
            try:
                year = int(row['季度'].split('年')[0])
                q = int(row['季度'].split('第')[1][0])
                return pd.Timestamp(year=year, month=q*3-2, day=1)
            except:
                return pd.Timestamp.now()
        gdp_df['季度日期'] = gdp_df.apply(parse_quarter, axis=1)
    
    print("\n" + "="*60)
    print("  📈 最新宏观数据")
    print("="*60)
    if not cpi_df.empty:
        latest_cpi = cpi_df.iloc[-1]
        if '全国-当月' in latest_cpi:
            print(f"📊 CPI数据日期: {latest_cpi['日期'].strftime('%Y年%m月') if pd.notna(latest_cpi['日期']) else 'N/A'} | 值: {latest_cpi['全国-当月']:.2f}%")
    
    if not gdp_df.empty and '季度' in gdp_df.columns:
        print("\n📈 GDP增速历史：")
        for _, row in gdp_df.sort_values('季度日期').tail(4).iterrows():
            quarter = row['季度'].replace("年第", "Q").replace("季度", "")
            print(f"   {quarter}: 同比{row['国内生产总值-同比增长']:.2f}% 绝对值{row['国内生产总值-绝对值']/1e4:.2f}万亿")
    
    symbols = ["600489","600938","600919","601857","600600",
               "601088","002304","002007","600905","600048",
               "601872","601012","002737","600009","000538"]
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    
    print("\n" + "="*60)
    print(f"  📊 开始分析 {len(symbols)} 只股票")
    print("="*60)
    
    results = []
    failed_symbols = []

    def process_symbol(symbol):
        try:
            stock_name = DataCache.stock_names.get(symbol, "")
            df = fetch_stock_data(symbol, start_date, end_date)
            
            if df is None or df.empty:
                with print_lock:
                    print(f"⚠️ {symbol} 数据为空，跳过")
                return None
            
            df = calculate_indicators(df)
            signals = generate_signals(df)
            df = backtest_strategy(df, signals)
            
            latest_signal = signals.iloc[-1]['signal']
            latest_date = signals.index[-1].strftime('%Y-%m-%d')
            latest_price = df['close'].iloc[-1]
            
            action = "⏸️ 持有"
            if latest_signal == 1:
                action = "🟢 ★★★ 买入 ★★★"
            elif latest_signal == -1:
                action = "🔴 ▼▼▼ 卖出 ▼▼▼"
            
            latest_score = signals.iloc[-1]
            buy_threshold, sell_threshold = dynamic_threshold(df)
            
            output = [
                "\n" + "─"*60,
                f"📈 {stock_name} ({symbol})",
                f"📅 数据期间: {start_date} 至 {end_date}",
                f"\n【{latest_date} 操作建议】{action}",
                f"💰 当前价格: ¥{latest_price:.2f}",
                "\n【多维评分系统】",
                f"买入评分: {latest_score['buy_score']:.2f}/1.00 (阈值: {buy_threshold:.2f})",
                f"卖出压力: {latest_score['sell_pressure']:.2f}/1.00 (阈值: {sell_threshold:.2f})",
                "\n买入评分构成：",
                f"  MACD动量(0.3): {latest_score['macd_momentum']:.2f}",
                f"  BOLL通道(0.2): {latest_score['boll_score']:.2f}",
                f"  RSI背离(0.15): {latest_score['rsi_divergence']:.2f}",
                f"  量价配合(0.2): {latest_score['volume_score']:.2f}",
                f"  宏观因子(0.15): {latest_score['macro_score']:.2f}",
                "\n卖出压力构成：",
                f"  趋势衰减(0.1): {latest_score['trend_decay']:.2f}",
                f"  超买系数(0.1): {latest_score['overbought']:.2f}", 
                f"  资金流出(0.1): {latest_score['capital_outflow']:.2f}",
                f"  回撤压力(0.1): {latest_score['drawdown_pressure']:.2f}",
                f"\n📊 累计收益率: {df['cum_returns'].iloc[-1]:.2%}",
                "─"*60
            ]
            with print_lock:
                print('\n'.join(output))
            
            return {
                'symbol': symbol,
                'name': stock_name,
                'signal': latest_signal,
                'return': df['cum_returns'].iloc[-1]
            }
            
        except Exception as e:
            with print_lock:
                print(f"❌ 处理 {symbol} 时发生错误: {str(e)[:80]}")
            return None

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_symbol, symbol) for symbol in symbols]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"❌ 发生未知错误: {e}")
    
    print("\n" + "="*60)
    print("  📊 分析汇总")
    print("="*60)
    
    buy_count = sum(1 for r in results if r['signal'] == 1)
    sell_count = sum(1 for r in results if r['signal'] == -1)
    hold_count = sum(1 for r in results if r['signal'] == 0)
    
    print(f"  分析股票数量: {len(results)}")
    print(f"  🟢 买入信号: {buy_count} 只")
    print(f"  🔴 卖出信号: {sell_count} 只")
    print(f"  ⏸️ 持有观望: {hold_count} 只")
    
    if buy_count > 0:
        buy_stocks = [r for r in results if r['signal'] == 1]
        print(f"\n  🏆 推荐买入股票 (按收益率排序):")
        for stock in sorted(buy_stocks, key=lambda x: x['return'], reverse=True):
            print(f"     • {stock['name']} ({stock['symbol']}) - 收益率: {stock['return']:.2%}")
    
    print("\n" + "="*60)
    print("  ✅ 分析完成")
    print("="*60 + "\n")        