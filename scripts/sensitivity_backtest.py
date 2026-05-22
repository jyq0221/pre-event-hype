#!/usr/bin/env python3
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from backtest_pre_event_hype import (
    BacktestConfig,
    DATA_DIR,
    RESULT_DIR,
    backtest_event,
    format_percent_columns,
    load_or_fetch_prices,
    summarize,
)


def main() -> int:
    events = pd.read_csv(DATA_DIR / "events.csv", parse_dates=["event_date"])
    tickers = sorted(set(events["ticker"]) | {"QQQ"})
    start = events["event_date"].min().to_pydatetime() - timedelta(days=120)
    end = events["event_date"].max().to_pydatetime() + timedelta(days=20)
    prices = {ticker: load_or_fetch_prices(ticker, start, end, refresh=False) for ticker in tickers}

    rows = []
    detailed_frames = []
    for entry_days in [3, 5, 7, 10, 15]:
        for require_ma20 in [True, False]:
            config = BacktestConfig(
                entry_days_before_event=entry_days,
                max_pre_entry_runup=0.12,
                require_above_ma20=require_ma20,
                benchmark="QQQ",
                refresh_prices=False,
            )
            result = pd.DataFrame(
                [backtest_event(event, prices, config) for _, event in events.iterrows()]
            )
            trades = result[result["trade"]].copy()
            summary = summarize(trades)
            if summary.empty:
                continue
            all_row = summary[summary["bucket"].eq("all_trades")].iloc[0].to_dict()
            all_row["entry_days"] = entry_days
            all_row["require_ma20"] = require_ma20
            all_row["filter_label"] = "ma20_and_runup" if require_ma20 else "runup_only"
            rows.append(all_row)

            result["entry_days"] = entry_days
            result["require_ma20"] = require_ma20
            detailed_frames.append(result)

    sensitivity = pd.DataFrame(rows)
    column_order = [
        "entry_days",
        "filter_label",
        "events",
        "avg_return",
        "median_return",
        "win_rate",
        "avg_benchmark",
        "avg_abnormal",
        "median_abnormal",
        "avg_max_drawdown",
        "best_trade",
        "worst_trade",
    ]
    sensitivity = sensitivity[column_order].sort_values(["filter_label", "entry_days"])

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    sensitivity_path = RESULT_DIR / "backtest_sensitivity.csv"
    detailed_path = RESULT_DIR / "backtest_sensitivity_events.csv"
    markdown_path = RESULT_DIR / "backtest_sensitivity.md"

    sensitivity.to_csv(sensitivity_path, index=False)
    pd.concat(detailed_frames, ignore_index=True).to_csv(detailed_path, index=False)

    with markdown_path.open("w", encoding="utf-8") as handle:
        handle.write("# Backtest Sensitivity\n\n")
        handle.write("- Exit: previous trading day close before event date\n")
        handle.write("- Overheat filter: 10 trading day pre-entry runup <= 12%\n")
        handle.write("- `ma20_and_runup`: entry close must be above MA20 and not overheated\n")
        handle.write("- `runup_only`: ignores MA20 trend filter and only excludes overheated entries\n\n")
        handle.write(format_percent_columns(sensitivity).to_markdown(index=False))
        handle.write("\n")

    print(format_percent_columns(sensitivity).to_string(index=False))
    print(f"wrote: {sensitivity_path}")
    print(f"wrote: {detailed_path}")
    print(f"wrote: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
