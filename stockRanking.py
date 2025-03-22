import pandas as pd
import pandas_ta as ta
import akshare as ak
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import traceback
import threading

# ========== 数据获取模块 ==========
def fetch_stock_data(symbol, start_date, end_date):
    """通过AKShare获取股票历史数据（日线）"""
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
    df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }, inplace=True)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    return df

# ========== 指标计算模块 ==========
def calculate_indicators(df):
    """计算技术指标：均线、MACD、RSI、BOLL、成交量"""
    # 均线 (5日, 20日)
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
    
    # 成交量变化率
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
    
    return df.dropna()

# ========== 信号生成模块 ==========
# ========== 新增市场状态评估函数 ==========
def market_regime(df):
    """评估市场状态 (震荡/趋势)"""
    adx = df.ta.adx(length=14)
    return "trend" if adx['ADX_14'].iloc[-1] > 25 else "range"

# ========== 修改动态阈值函数 ==========
def dynamic_threshold(df):
    """双阈值动态调整机制"""
    regime = market_regime(df)
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

# 在generate_signals中添加实际宏观数据计算
# 修改get_macro_score中的CPI处理部分
def get_macro_score(date):
    """使用缓存的宏观数据"""
    try:
        # 从缓存获取数据
        cpi_df = DataCache.macro_data['cpi']
        
        # 转换为季度和月份用于宏观数据对齐
        quarter = (date.month - 1) // 3 + 1
        
        # 1. 获取CPI同比（月度）
        # 查找最近3个月的数据（处理数据延迟）
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
        fx_df = ak.fx_spot_quote()
        cny_rate = fx_df[fx_df['货币对'].str.contains('USD/CNY')].iloc[0]['买报价']
        fx_score = 1 - abs(cny_rate - 7)/0.5  # 6.7-7.3为合理区间
        
        # 3. 制造业PMI（月度）
        pmi_df = DataCache.macro_data['pmi']
        year_month = date.strftime("%Y年%m月")  # 新增这行定义
        pmi_current = pmi_df[pmi_df['月份'] == year_month]['制造业-指数'].values
        pmi_score = 0.0 if len(pmi_current) == 0 else (float(pmi_current[0]) - 45)/15  # 45-60为合理区间
        
        # 4. GDP增速（季度）
        gdp_df = ak.macro_china_gdp()
        # 从季度字段提取年份（原数据季度格式为"2023年4季度"）
        gdp_df['年份'] = gdp_df['季度'].str.split('年').str[0].astype(int)
        quarter_str = f"{date.year}年第{quarter}季度"  # 生成季度字符串匹配格式
        
        # 使用季度字符串进行匹配
        gdp_current = gdp_df[(gdp_df['季度'].str.contains(quarter_str))]['国内生产总值-绝对值'].values
        
        gdp_growth = 0.0 if len(gdp_current) < 2 else (gdp_current[0]/gdp_current[1] - 1)
        gdp_score = min(max((gdp_growth - 4)/2, 0), 1)  # 4%-6%为合理区间
        
        # 加权综合评分（总权重0.15）
        weights = [0.3, 0.3, 0.2, 0.2]  # CPI:30% 汇率:30% PMI:20% GDP:20%
        total_score = (cpi_score*weights[0] + fx_score*weights[1] + 
                      pmi_score*weights[2] + gdp_score*weights[3]) * 0.15
        
        return max(min(total_score, 0.15), 0)  # 确保在0-0.15区间
        
    except Exception as e:
        print(f"宏观数据获取失败: {str(e)}")
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

# 修改主程序中的宏观数据打印部分
# ========== 修改主程序中的宏观数据获取部分 ==========
if __name__ == "__main__":
    # 预先获取全局共享数据
    DataCache.stock_names = dict(zip(ak.stock_info_a_code_name()['code'], ak.stock_info_a_code_name()['name']))
    
    # 预先获取宏观数据（每日仅更新一次）
    try:
        # 使用更稳健的CPI获取方式
        DataCache.macro_data = {
            'cpi': ak.macro_china_cpi() if not pd.DataFrame(ak.macro_china_cpi()).empty else pd.DataFrame(),
            'fx': ak.fx_spot_quote(),
            'pmi': ak.macro_china_pmi(),
            'gdp': ak.macro_china_gdp()
        }
    except Exception as e:
        print(f"宏观数据获取失败，使用本地缓存数据: {str(e)}")
        # 加载本地备份数据（需要提前准备）
        DataCache.macro_data = pd.read_pickle('macro_backup.pkl')

    # 新增：处理空的CPI数据情况
    if DataCache.macro_data['cpi'].empty:
        print("警告：CPI数据获取失败，使用最近有效数据")
        DataCache.macro_data['cpi'] = pd.DataFrame({
            '日期': [datetime.now().strftime("%Y年%m月")],
            '全国-当月': [2.5]  # 默认值
        })

    # 新增：处理宏观数据日期格式
    cpi_df = DataCache.macro_data['cpi']
    cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月')
    cpi_df.sort_values('日期', inplace=True)
    
    # 修改主程序中的GDP日期处理部分
    if __name__ == "__main__":
        # 创建全局打印锁
        print_lock = threading.Lock()  # 新增锁对象
        
        # 修正后的GDP季度日期处理
        gdp_df = DataCache.macro_data['gdp']
        
        # 使用更稳健的季度解析方法
        def parse_quarter(row):
            year = int(row['季度'].split('年')[0])
            q = int(row['季度'].split('第')[1][0])
            return pd.Timestamp(year=year, month=q*3-2, day=1)  # 将季度转换为该季第一个月
            
        gdp_df['季度日期'] = gdp_df.apply(parse_quarter, axis=1)
        
        print("\n=== 最新宏观数据 ===")
        # 打印最新CPI数据
        latest_cpi = cpi_df.iloc[-1]
        print(f"CPI数据日期: {latest_cpi['日期'].strftime('%Y年%m月')} | 值: {latest_cpi.iloc[3]:.2f}%")
        
        # 打印GDP增速数据（最近4个季度）
        print("\nGDP增速历史：")
        for _, row in gdp_df.sort_values('季度日期').tail(4).iterrows():
            quarter = row['季度'].replace("年第", "Q").replace("季度", "")
            # 修正单位转换（原数据单位为亿元，1万亿=10000亿）
            print(f"{quarter}: 同比{row['国内生产总值-同比增长']:.2f}% 绝对值{row['国内生产总值-绝对值']/1e4:.2f}万亿")
        # 三个实验组：粗排高信号；持有观测；粗排信号+自选低位股
        symbols = ["600489","600938","600919","601857","600600",
                   "601088","002304","002007","600905","600048",
                   "601872","601012","002737","600009","000538"]
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        
        # 获取股票名称映射
        stock_code_name_df = ak.stock_info_a_code_name()
        code_name_dict = dict(zip(stock_code_name_df['code'], stock_code_name_df['name']))

        def process_symbol(symbol):
            try:
                stock_name = code_name_dict.get(symbol, "")
                df = fetch_stock_data(symbol, start_date, end_date)
                df = calculate_indicators(df)
                signals = generate_signals(df)
                df = backtest_strategy(df, signals)
                
                latest_signal = signals.iloc[-1]['signal']
                latest_date = signals.index[-1].strftime('%Y-%m-%d')
                latest_price = df['close'].iloc[-1]
                
                # 买卖建议
                action = "持有"
                if latest_signal == 1:
                    action = "★★★ 买入 ★★★"
                elif latest_signal == -1:
                    action = "▼▼▼ 卖出 ▼▼▼"
                
                # 评分详情
                latest_score = signals.iloc[-1]
                
                # 在生成信号后获取动态阈值
                buy_threshold, sell_threshold = dynamic_threshold(df)
                
                # 构建输出内容（原所有print语句改为列表追加）
                output = [
                    "\n" + "="*40,
                    f"股票名称: {stock_name}({symbol})",
                    f"数据期间: {start_date} 至 {end_date}",
                    f"\n【{latest_date} 操作建议】{action}",
                    f"当前价格: {latest_price:.2f}",
                     "\n【多维评分系统】",
                    f"买入评分: {latest_score['buy_score']:.2f}/1.00  (当前阈值: {buy_threshold:.2f})",
                    f"卖出压力: {latest_score['sell_pressure']:.2f}/1.00  (当前阈值: {sell_threshold:.2f})",
                    "\n买入评分构成：",
                    f"MACD动量(0.3): {latest_score['macd_momentum']:.2f}",
                    f"BOLL通道(0.2): {latest_score['boll_score']:.2f}",
                    f"RSI背离(0.15): {latest_score['rsi_divergence']:.2f}",
                    f"量价配合(0.2): {latest_score['volume_score']:.2f}",
                    f"宏观因子(0.15): {latest_score['macro_score']:.2f}",
                    "\n卖出压力构成：",
                    f"趋势衰减(0.1): {latest_score['trend_decay']:.2f}",
                    f"超买系数(0.1): {latest_score['overbought']:.2f}", 
                    f"资金流出(0.1): {latest_score['capital_outflow']:.2f}",
                    f"回撤压力(0.1): {latest_score['drawdown_pressure']:.2f}",
                    f"\n累计收益率: {df['cum_returns'].iloc[-1]:.2%}",
                    "="*40
                ]
                # 原子化输出
                with print_lock:
                    print('\n'.join(output))
                
            except Exception as e:
                print(f"处理{symbol}时发生错误: {str(e)}")

        # 使用多线程加速（正确缩进）
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(process_symbol, symbol) for symbol in symbols]
            for future in as_completed(futures):
                try:
                    future.result()
                except KeyboardInterrupt:
                    print("用户手动中断，正在优雅关闭...")
                # 这里可以添加更多资源清理的代码，例如关闭文件、数据库连接等
                    sys.exit(1)
                except Exception as e:
                    print(f"发生未知错误: {e}")
                    traceback.print_exc()        