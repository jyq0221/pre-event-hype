# Pre-Event Hype Strategy

科技公司发布会前预期交易策略研究。

核心思想：在科技公司重要发布会前买入，发布会前一交易日或发布会当天开盘前退出，只交易发布会前的关注度和预期升温，不赌发布会内容本身。

## 当前内容

- `Pre-Event-Hype-Strategy.md`：策略设计文档
- `Backtest-Results.md`：第一版简单回测报告
- `data/events.csv`：历史发布会事件样本
- `data/prices/`：Yahoo Finance 日线价格缓存
- `scripts/backtest_pre_event_hype.py`：基础回测脚本
- `scripts/sensitivity_backtest.py`：参数敏感性测试脚本
- `results/`：回测输出结果

## 运行方式

```bash
python3 scripts/backtest_pre_event_hype.py
python3 scripts/sensitivity_backtest.py
```

如需重新抓取价格数据：

```bash
python3 scripts/backtest_pre_event_hype.py --refresh-prices
```

## 当前初步结论

第一版样本包含 35 个科技发布会事件。基础规则为 T-7 买入、发布会前一交易日收盘退出、入场价高于 MA20、前 10 日涨幅不超过 12%。

基础回测结果：

- 过滤后交易：20 笔
- 平均收益：1.92%
- 中位数收益：1.94%
- 胜率：65.00%
- 平均超额收益：0.46% vs QQQ

初步看，AI / GPU / 半导体相关发布会前的预期交易更明显；普通消费电子新品发布会和大型平台开发者大会的效果较弱。

## 免责声明

本仓库仅用于策略研究和回测实验，不构成投资建议。
