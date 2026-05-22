#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PRICE_DIR = DATA_DIR / "prices"
RESULT_DIR = ROOT / "results"


@dataclass(frozen=True)
class BacktestConfig:
    entry_days_before_event: int = 7
    max_pre_entry_runup: float = 0.12
    require_above_ma20: bool = True
    benchmark: str = "QQQ"
    refresh_prices: bool = False


def yahoo_chart_url(ticker: str, start: datetime, end: datetime) -> str:
    params = {
        "period1": int(start.replace(tzinfo=timezone.utc).timestamp()),
        "period2": int(end.replace(tzinfo=timezone.utc).timestamp()),
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?{urllib.parse.urlencode(params)}"


def fetch_yahoo_prices(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    request = urllib.request.Request(
        yahoo_chart_url(ticker, start, end),
        headers={"User-Agent": "Mozilla/5.0 pre-event-hype-backtest/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result["indicators"]["quote"][0]
    adjclose = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])

    rows = []
    for i, ts in enumerate(timestamps):
        close = quote["close"][i]
        if close is None:
            continue
        adjusted = adjclose[i] if i < len(adjclose) and adjclose[i] is not None else close
        rows.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                "open": quote["open"][i],
                "high": quote["high"][i],
                "low": quote["low"][i],
                "close": close,
                "adj_close": adjusted,
                "volume": quote["volume"][i],
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"No price rows returned for {ticker}")
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return frame


def load_or_fetch_prices(
    ticker: str, start: datetime, end: datetime, refresh: bool
) -> pd.DataFrame:
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    path = PRICE_DIR / f"{ticker}.csv"
    if path.exists() and not refresh:
        frame = pd.read_csv(path, parse_dates=["date"])
    else:
        frame = fetch_yahoo_prices(ticker, start, end)
        frame.to_csv(path, index=False)
        time.sleep(0.25)

    frame = frame.sort_values("date").reset_index(drop=True)
    frame["ma20"] = frame["adj_close"].rolling(20).mean()
    frame["ret_10d"] = frame["adj_close"].pct_change(10)
    return frame


def pct_return(frame: pd.DataFrame, entry_date: pd.Timestamp, exit_date: pd.Timestamp) -> float:
    entry = frame.loc[frame["date"].eq(entry_date), "adj_close"]
    exit_ = frame.loc[frame["date"].eq(exit_date), "adj_close"]
    if entry.empty or exit_.empty:
        return math.nan
    return float(exit_.iloc[0] / entry.iloc[0] - 1.0)


def backtest_event(
    event: pd.Series,
    prices: dict[str, pd.DataFrame],
    config: BacktestConfig,
) -> dict[str, object]:
    ticker = event["ticker"]
    stock = prices[ticker]
    benchmark = prices[config.benchmark]
    event_date = pd.Timestamp(event["event_date"])

    pre_event = stock[stock["date"] < event_date].reset_index(drop=True)
    if len(pre_event) < config.entry_days_before_event + 20:
        return {
            **event.to_dict(),
            "trade": False,
            "skip_reason": "insufficient_history",
        }

    entry_idx = len(pre_event) - config.entry_days_before_event
    exit_idx = len(pre_event) - 1
    entry_row = pre_event.iloc[entry_idx]
    exit_row = pre_event.iloc[exit_idx]

    entry_date = entry_row["date"]
    exit_date = exit_row["date"]
    above_ma20 = bool(entry_row["adj_close"] > entry_row["ma20"])
    pre_entry_runup = float(entry_row["ret_10d"]) if pd.notna(entry_row["ret_10d"]) else math.nan

    filters = []
    if config.require_above_ma20 and not above_ma20:
        filters.append("below_ma20")
    if pd.notna(pre_entry_runup) and pre_entry_runup > config.max_pre_entry_runup:
        filters.append("overheated")

    strategy_return = pct_return(stock, entry_date, exit_date)
    benchmark_return = pct_return(benchmark, entry_date, exit_date)
    abnormal_return = strategy_return - benchmark_return

    holding = stock[(stock["date"] >= entry_date) & (stock["date"] <= exit_date)].copy()
    running = holding["adj_close"] / float(entry_row["adj_close"]) - 1.0
    max_drawdown = float(running.min())

    return {
        **event.to_dict(),
        "trade": len(filters) == 0,
        "skip_reason": "|".join(filters),
        "entry_date": entry_date.date().isoformat(),
        "exit_date": exit_date.date().isoformat(),
        "entry_adj_close": float(entry_row["adj_close"]),
        "exit_adj_close": float(exit_row["adj_close"]),
        "strategy_return": strategy_return,
        "benchmark_return": benchmark_return,
        "abnormal_return": abnormal_return,
        "max_drawdown": max_drawdown,
        "above_ma20": above_ma20,
        "pre_entry_runup_10d": pre_entry_runup,
        "holding_days": int((exit_idx - entry_idx) + 1),
    }


def summarize(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    def row(label: str, frame: pd.DataFrame) -> dict[str, object]:
        return {
            "bucket": label,
            "events": int(len(frame)),
            "avg_return": frame["strategy_return"].mean(),
            "median_return": frame["strategy_return"].median(),
            "win_rate": (frame["strategy_return"] > 0).mean(),
            "avg_benchmark": frame["benchmark_return"].mean(),
            "avg_abnormal": frame["abnormal_return"].mean(),
            "median_abnormal": frame["abnormal_return"].median(),
            "avg_max_drawdown": frame["max_drawdown"].mean(),
            "best_trade": frame["strategy_return"].max(),
            "worst_trade": frame["strategy_return"].min(),
        }

    rows = [row("all_trades", trades)]
    rows.extend(row(ticker, group) for ticker, group in trades.groupby("ticker"))
    rows.extend(row(event_type, group) for event_type, group in trades.groupby("event_type"))
    return pd.DataFrame(rows)


def format_percent_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    percent_cols = [
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
    for col in percent_cols:
        if col in out.columns:
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else f"{x:.2%}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default=str(DATA_DIR / "events.csv"))
    parser.add_argument("--refresh-prices", action="store_true")
    parser.add_argument("--entry-days", type=int, default=7)
    parser.add_argument("--max-runup", type=float, default=0.12)
    args = parser.parse_args()

    config = BacktestConfig(
        entry_days_before_event=args.entry_days,
        max_pre_entry_runup=args.max_runup,
        refresh_prices=args.refresh_prices,
    )

    events = pd.read_csv(args.events, parse_dates=["event_date"])
    tickers = sorted(set(events["ticker"]) | {config.benchmark})
    start = events["event_date"].min().to_pydatetime() - timedelta(days=120)
    end = events["event_date"].max().to_pydatetime() + timedelta(days=20)

    prices = {}
    for ticker in tickers:
        prices[ticker] = load_or_fetch_prices(ticker, start, end, config.refresh_prices)

    rows = [backtest_event(event, prices, config) for _, event in events.iterrows()]
    results = pd.DataFrame(rows)
    trades = results[results["trade"]].copy()
    summary = summarize(trades)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULT_DIR / "backtest_events.csv"
    trades_path = RESULT_DIR / "backtest_trades.csv"
    summary_path = RESULT_DIR / "backtest_summary.csv"
    markdown_path = RESULT_DIR / "backtest_summary.md"

    results.to_csv(results_path, index=False)
    trades.to_csv(trades_path, index=False)
    summary.to_csv(summary_path, index=False)

    with markdown_path.open("w", encoding="utf-8") as handle:
        handle.write("# Pre-Event Hype Strategy Simple Backtest\n\n")
        handle.write(f"- Events in sample: {len(results)}\n")
        handle.write(f"- Trades after filters: {len(trades)}\n")
        handle.write(f"- Entry: T-{config.entry_days_before_event} trading day close\n")
        handle.write("- Exit: previous trading day close before event date\n")
        handle.write("- Filters: entry close > MA20, 10 trading day pre-entry runup <= 12%\n\n")
        handle.write("## Summary\n\n")
        handle.write(format_percent_columns(summary).to_markdown(index=False))
        handle.write("\n\n## Trades\n\n")
        trade_cols = [
            "ticker",
            "event_name",
            "event_date",
            "entry_date",
            "exit_date",
            "strategy_return",
            "benchmark_return",
            "abnormal_return",
            "max_drawdown",
        ]
        printable = trades[trade_cols].copy()
        for col in ["strategy_return", "benchmark_return", "abnormal_return", "max_drawdown"]:
            printable[col] = printable[col].map(lambda x: f"{x:.2%}")
        handle.write(printable.to_markdown(index=False))
        handle.write("\n")

    print(f"events: {len(results)}")
    print(f"trades: {len(trades)}")
    if not summary.empty:
        print(format_percent_columns(summary.head(20)).to_string(index=False))
    print(f"wrote: {results_path}")
    print(f"wrote: {trades_path}")
    print(f"wrote: {summary_path}")
    print(f"wrote: {markdown_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"network error while fetching prices: {exc}", file=sys.stderr)
        raise SystemExit(2)
