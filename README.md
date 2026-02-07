# Stock Science - 股票策略分析系统

## 全局说明

本项目经过优化升级，添加了轻量级改进方案，提升了用户体验和系统稳定性。

### 核心升级
- ✅ 添加进度显示功能
- ✅ 添加结果自动保存到CSV
- ✅ 添加简单统计报告
- ✅ 保留原始并发速度（8线程，无限流）
- ✅ 简单错误处理机制

### 推荐使用
- **StockPre**: 使用 `stockPre_lite.py`（轻量级改进版）
- **StockGrain**: 使用 `stock_grain_ranking/main_lite.py`（轻量级改进版）

### 版本说明
- v1.0 (2026-02-07): 初始版本
- v1.1 (2026-02-07): 添加轻量级改进方案（推荐）

---

## 项目概述

本项目是一个基于技术分析的股票策略系统，包含两个主要模块：
- **StockPre**: 沪深300成分股筛选系统
- **Stock Grain Ranking**: 多维评分股票分析系统

## 文件说明

### 推荐使用文件（生产环境）

| 文件 | 说明 | 用途 |
|------|------|------|
| [stockPre.py](stockPre.py) | StockPre原始版本 | 基础版本 |
| [stockPre_lite.py](stockPre_lite.py) | StockPre轻量级改进版 | **推荐使用** ⭐ |
| [stock_grain_ranking/main.py](stock_grain_ranking/main.py) | StockGrain原始版本 | 基础版本 |
| [stock_grain_ranking/main_lite.py](stock_grain_ranking/main_lite.py) | StockGrain轻量级改进版 | **推荐使用** ⭐ |

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
- v1.1 (2026-02-07): 添加轻量级改进方案（推荐）

## 许可证

本项目仅供学习和研究使用。

---

**最后更新**: 2026-02-07
