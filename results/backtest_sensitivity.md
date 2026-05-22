# Backtest Sensitivity

- Exit: previous trading day close before event date
- Overheat filter: 10 trading day pre-entry runup <= 12%
- `ma20_and_runup`: entry close must be above MA20 and not overheated
- `runup_only`: ignores MA20 trend filter and only excludes overheated entries

|   entry_days | filter_label   |   events | avg_return   | median_return   | win_rate   | avg_benchmark   | avg_abnormal   | median_abnormal   | avg_max_drawdown   | best_trade   | worst_trade   |
|-------------:|:---------------|---------:|:-------------|:----------------|:-----------|:----------------|:---------------|:------------------|:-------------------|:-------------|:--------------|
|            3 | ma20_and_runup |       18 | 1.61%        | 1.22%           | 72.22%     | 1.00%           | 0.61%          | 0.28%             | -0.57%             | 8.20%        | -2.93%        |
|            5 | ma20_and_runup |       21 | 0.93%        | 1.96%           | 61.90%     | 1.00%           | -0.08%         | 0.28%             | -1.72%             | 9.93%        | -8.68%        |
|            7 | ma20_and_runup |       20 | 1.92%        | 1.94%           | 65.00%     | 1.46%           | 0.46%          | 0.27%             | -1.83%             | 12.78%       | -8.17%        |
|           10 | ma20_and_runup |       16 | 0.91%        | 2.07%           | 56.25%     | 0.95%           | -0.04%         | -0.24%            | -2.33%             | 4.88%        | -7.59%        |
|           15 | ma20_and_runup |       16 | 4.04%        | 4.42%           | 62.50%     | 2.03%           | 2.01%          | 2.00%             | -2.54%             | 16.35%       | -10.69%       |
|            3 | runup_only     |       32 | 0.99%        | 0.92%           | 65.62%     | 0.44%           | 0.54%          | 0.51%             | -0.86%             | 8.20%        | -5.01%        |
|            5 | runup_only     |       33 | 1.26%        | 1.47%           | 63.64%     | 0.52%           | 0.75%          | 0.95%             | -1.88%             | 16.37%       | -8.68%        |
|            7 | runup_only     |       33 | 2.59%        | 1.99%           | 66.67%     | 1.45%           | 1.13%          | 0.30%             | -1.93%             | 20.97%       | -8.17%        |
|           10 | runup_only     |       31 | 2.80%        | 2.30%           | 67.74%     | 1.72%           | 1.08%          | 0.38%             | -2.08%             | 24.26%       | -7.59%        |
|           15 | runup_only     |       32 | 2.86%        | 3.17%           | 59.38%     | 1.49%           | 1.37%          | 1.21%             | -3.96%             | 16.35%       | -10.69%       |
