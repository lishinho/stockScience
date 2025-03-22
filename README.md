# stockScience
stockScience

## How to run
### stock_grain_ranking: python main.py -s 股票代码 -b 开始日期
例如：python main.py -s 600489 601088 -b 20240501

这是一个基于多维评分模型的股票交易策略系统，主要包含以下核心模块：

## 一、数据获取模块

```python
def fetch_stock_data(symbol, start_date, end_date):
    """通过AKShare获取股票历史数据（日线）"""
    # 获取开盘价、收盘价、成交量等基础数据
    # 进行列名转换和日期格式化
```

## 二、技术指标计算模块

```python
def calculate_indicators(df):
    """计算技术指标：均线、MACD、RSI、BOLL、成交量"""
    # 包含5/20日均线、MACD、RSI、布林带等指标
    # 计算成交量3日均线及变化率
```

## 三、信号生成系统
### 1. 市场状态评估

```python
def market_regime(df):
    """通过ADX指标判断趋势/震荡市"""
    # ADX >25为趋势市，否则为震荡市
```

### 2. 动态阈值调整

```python
def dynamic_threshold(df):
    """根据市场波动率动态调整买卖阈值"""
    # 趋势市：买入阈值0.58-0.62，卖出阈值0.12
    # 震荡市：买入阈值0.63-0.66，卖出阈值0.1
```

### 3. 多维评分模型

```python
def generate_signals(df):
    """核心信号生成逻辑"""
    # 买入评分包含：
    - MACD动量 (30%)
    - 布林带位置 (20%)
    - RSI超卖 (15%)
    - 量能配合 (20%)
    - 宏观因子 (15%)

    # 卖出压力包含：
    - 趋势衰减 (10%)
    - 超买系数 (10%)
    - 资金流出 (10%)
    - 回撤压力 (10%)
```

## 四、宏观数据整合

```python
def get_macro_score(date):
    """整合CPI、汇率、PMI、GDP等宏观数据"""
    # 使用加权评分机制（CPI 30% + 汇率30% + PMI20% + GDP20%）
    # 数据缓存机制提升性能
```

## 五、风险控制模块

```python
def risk_management(df):
    """动态风控机制"""
    # 10%最大回撤暂停交易
    # 近3次交易2次止损暂停交易
```

## 六、回测系统

```python
def backtest_strategy(df, signals):
    """策略回测引擎"""
    # 包含信号延迟处理（shift(1)）
    # 整合风控模块
```

## 七、主程序特性
- 并行处理：使用线程池加速多股票分析
- 数据缓存：全局缓存宏观数据和股票名称
- 原子化输出：使用打印锁保证多线程输出完整性
- 异常处理：完善的错误捕捉和备用数据机制

### 策略逻辑流程图

```
数据获取 → 指标计算 → 市场状态判断 → 动态阈值 → 多维评分 
→ 信号生成 → 风险控制 → 回测验证 → 结果输出
```
该系统的核心创新点在于将技术指标、宏观因子、市场状态和动态阈值进行量化整合，通过多维度评分机制生成交易信号，同时配备严格的风控措施。
该系统实现了技术面与基本面的量化融合，通过动态调整机制增强策略适应性，适合中短线交易决策。

### stock_pre_ranking 
1. cd stock_pre_ranking
2. pip install -r requirements.txt
3. python main.py