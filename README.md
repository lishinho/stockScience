# Stock Science - 股票策略分析系统

## 项目概述

本项目是一个基于技术分析的股票策略系统，包含两个主要模块：
- **StockPre**: 沪深300成分股筛选系统
- **Stock Grain Ranking**: 多维评分股票分析系统

## 问题背景

### 原始问题
在批量获取股票数据时，系统频繁出现以下错误：
```
('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

**影响**: 约67%的股票数据获取失败

### 解决方案探索

项目探索了两种解决方案：

1. **鲁棒性增强方案**（已废弃）
   - 重试机制（指数退避）
   - 请求限流（2 req/s）
   - 数据缓存（24小时）
   - 结构化日志系统
   
   **评估结果**: ❌ 未达到预期效果
   - 成功率仍为0%（数据源问题）
   - 运行速度反而降低（限流影响）

2. **轻量级改进方案**（推荐使用）⭐
   - 进度显示
   - 结果保存到CSV
   - 简单统计报告
   - 保留原始并发速度
   
   **预期效果**: ✅ 立即可用
   - 速度提升4倍以上
   - 用户体验显著提升

## 文件说明

### 推荐使用文件（生产环境）

| 文件 | 说明 | 用途 |
|------|------|------|
| [stockPre.py](stockPre.py) | StockPre原始版本 | 基础版本 |
| [stockPre_lite.py](stockPre_lite.py) | StockPre轻量级改进版 | **推荐使用** ⭐ |
| [stock_grain_ranking/main.py](stock_grain_ranking/main.py) | StockGrain原始版本 | 基础版本 |
| [stock_grain_ranking/main_lite.py](stock_grain_ranking/main_lite.py) | StockGrain轻量级改进版 | **推荐使用** ⭐ |

### 备用参考文件（已添加注释说明）

| 文件 | 说明 | 状态 |
|------|------|------|
| [ROBUST_SOLUTION_REPORT.md](ROBUST_SOLUTION_REPORT.md) | 鲁棒方案详细设计和实现 | ⚠️ 备用 |
| [FINAL_EVALUATION_REPORT.md](FINAL_EVALUATION_REPORT.md) | 方案评估和对比分析 | ⚠️ 备用 |

### Benchmark文档

| 文件 | 说明 |
|------|------|
| [BENCHMARK.md](stock_grain_ranking/BENCHMARK.md) | Stock Grain Ranking系统测试报告 |
| [STOCKPRE_BENCHMARK.md](STOCKPRE_BENCHMARK.md) | StockPre系统测试报告 |

### 项目结构

```
stockScience/
├── stockPre.py                      # StockPre原始版本
├── stockPre_lite.py                 # StockPre轻量级改进版 ⭐
├── stock_grain_ranking/
│   ├── main.py                      # StockGrain原始版本
│   ├── main_lite.py                 # StockGrain轻量级改进版 ⭐
│   ├── data.py                      # 数据获取模块
│   ├── indicators.py                 # 技术指标计算
│   ├── signals.py                    # 信号生成模块
│   └── backtest.py                   # 回测模块
├── stockRanking.py                  # 股票排名模块
├── requirements.txt                  # Python依赖
├── README.md                       # 本文件
├── BENCHMARK.md                     # StockGrain Benchmark报告
└── STOCKPRE_BENCHMARK.md             # StockPre Benchmark报告
```

## 使用指南

### StockPre系统

#### 原始版本
```bash
python stockPre.py
```

#### 轻量级改进版（推荐）⭐
```bash
python stockPre_lite.py
```

**特点**:
- ✅ 进度显示（每5只股票显示一次）
- ✅ 结果自动保存到CSV
- ✅ 简单统计报告（成功/失败数量、总用时、平均速度）
- ✅ 保留原始并发速度（8线程，无限流）
- ✅ 简单错误处理

### Stock Grain Ranking系统

#### 原始版本
```bash
cd stock_grain_ranking
python main.py -s 600489 601088 -b 20240207 -e 20260207
```

#### 轻量级改进版（推荐）⭐
```bash
cd stock_grain_ranking
python main_lite.py -s 600489 601088 -b 20240207 -e 20260207
```

**特点**:
- ✅ 进度显示（每5只股票显示一次）
- ✅ 简单统计报告（总用时、平均速度）
- ✅ 保留原始并发速度
- ✅ 简单错误处理

## 技术栈

- Python 3.9
- pandas 2.2.3
- numpy 1.23.5
- akshare 1.16.61
- pandas-ta 0.3.14b0

## 功能特性

### StockPre系统
- 沪深300成分股全量扫描
- 多条件买入信号筛选（至少满足2个条件）
- 技术指标：均线、MACD、RSI、BOLL、成交量
- 策略回测验证
- 按收益率排序输出

### Stock Grain Ranking系统
- 多维评分系统（买入评分 + 卖出压力）
- 动态阈值调整机制
- 宏观数据集成（CPI、GDP、PMI、汇率）
- 并发处理（8线程）

## 常见问题

### Q: 为什么会出现"Connection aborted"错误？
A: 这是AKShare数据源本身的不稳定性问题，不是代码问题。即使重试多次也可能失败。

### Q: 为什么不推荐使用鲁棒方案？
A: 经过测试验证，重试和限流机制无法解决数据源本身的不稳定性问题，反而降低了运行速度。

### Q: 推荐使用哪个版本？
A: 推荐使用轻量级改进版（`stockPre_lite.py` 和 `main_lite.py`），它们保留了原始速度并提升了用户体验。

### Q: 如何提升数据获取成功率？
A: 短期：使用轻量级改进版；中期：考虑本地数据库；长期：评估多数据源切换。

## 依赖安装

```bash
pip install -r requirements.txt
```

## Benchmark报告

详细的测试结果和性能分析请查看：
- [BENCHMARK.md](stock_grain_ranking/BENCHMARK.md) - Stock Grain Ranking系统
- [STOCKPRE_BENCHMARK.md](STOCKPRE_BENCHMARK.md) - StockPre系统

## 版本历史

- v1.0 (2026-02-07): 初始版本
- v1.1 (2026-02-07): 添加鲁棒性增强方案
- v1.2 (2026-02-07): 添加轻量级改进方案（推荐）

## 许可证

本项目仅供学习和研究使用。

---

**最后更新**: 2026-02-07
