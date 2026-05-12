from __future__ import absolute_import, division, print_function, unicode_literals

"""
this is what will eventually be maxStressRun.py, but the difference is that we put the wrappers in
this file instead of putting them on the cerebro.py

maxStressRun.py — Maximum-load energy benchmark for the backtrader _runnext loop.

Saturates every instrumented section independently:

  strategy_next  — 20 SMAs, 20 EMAs, 10 RSIs, 5 MACDs, 5 BollingerBands,
                   5 ATRs, 5 Stochastics, 10 CrossOvers  +  Python-level
                   iteration over all indicator values in next().

  broker         — self.close() + 3 new orders (market + limit + stop) on
                   every single bar, forcing the broker to match and cancel
                   pending orders each iteration.

  cheat_on_open  — next_open() is implemented and cerebro.broker.set_coo(True)
                   is set, making the cheat_on_open section non-trivial.

  data_feed      — 3 symbols (ORCL, NVDA, YHOO) each resampled to weekly and
                   monthly → 9 feeds total processed per bar.

  notifications  — 10 store callbacks + 10 data callbacks registered.
                   In historical mode the notification queues are mostly empty,
                   but the dispatch overhead still scales with callback count.
"""

import datetime
import sys
import os
import subprocess
import codecarbon

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import backtrader as bt

# ── Run parameters (mirror tutorialRun.py) ──────────────────────────────────
N_RUNS = 10
FROM_DATE = datetime.datetime(1999, 1, 1) # 1999: earliest date shared by all 3 feeds

#FROM_DATE = datetime.datetime(2014, 12, 30) #debuggin for the mac
TO_DATE = datetime.datetime(2014, 12, 31)


# ── Notification callbacks ───────────────────────────────────────────────────
# Registered 10× each to stress the callback-dispatch loops inside
# _storenotify() and _datanotify().  They do no real work so they add pure
# dispatch overhead, not confounding computation.


def _noop_store_cb(msg, *args, **kwargs):
    pass


def _noop_data_cb(data, status, *args, **kwargs):
    pass

class MaxStressStrategy(bt.Strategy):
    """
    Pushes every section of the _runnext loop to its maximum.

    __init__  builds a deep indicator graph so that each bar triggers the
              maximum amount of cascaded indicator computation.

    next()    iterates every indicator value in Python (no early-out) then
              places 3 orders per bar to maximise broker work.

    next_open() runs before the broker when cheat_on_open=True, contributing
                to the cheat_on_open section timing.
    """

    def __init__(self):
        d = self.data  # primary data feed (ORCL daily)

        # ── Moving averages: 20 periods each ────────────────────────────────
        sma_periods = range(5, 205, 10)  # [5, 15, 25, … 195]  → 20 indicators
        ema_periods = range(5, 205, 10)  # 20 indicators

        self.smas = [bt.ind.SMA(d, period=p) for p in sma_periods]
        self.emas = [bt.ind.EMA(d, period=p) for p in ema_periods]

        # ── RSI: 10 periods ─────────────────────────────────────────────────
        rsi_periods = range(5, 55, 5)  # [5, 10, 15, … 50]  → 10 indicators
        self.rsiz = [bt.ind.RSI(d, period=p) for p in rsi_periods]

        # ── MACD: 5 instances (uses EMA internally → cascaded work) ─────────
        self.macds = [bt.ind.MACD(d) for _ in range(5)]

        # ── BollingerBands: 5 periods ────────────────────────────────────────
        bb_periods = range(10, 60, 10)  # [10, 20, 30, 40, 50]  → 5 indicators
        self.bbs = [bt.ind.BollingerBands(d, period=p) for p in bb_periods]

        # ── ATR: 5 periods ───────────────────────────────────────────────────
        atr_periods = range(5, 30, 5)  # [5, 10, 15, 20, 25]  → 5 indicators
        self.atrs = [bt.ind.ATR(d, period=p) for p in atr_periods]

        # ── Stochastic: 5 instances ──────────────────────────────────────────
        self.stochs = [bt.ind.Stochastic(d) for _ in range(5)]

        # ── CrossOver: 10 signals (depend on SMAs + EMAs → cascaded) ────────
        self.crosses = [
            bt.ind.CrossOver(s, e) for s, e in zip(self.smas[:10], self.emas[:10])
        ]

    # ── Bar processing (strategy_next + broker saturation) ──────────────────

    def next(self):
        # -- Python-level iteration: prevents the interpreter from short-
        #    circuiting and forces every indicator value to be materialised.
        score = sum(s[0] - e[0] for s, e in zip(self.smas, self.emas))
        rsi_mean = sum(r[0] for r in self.rsiz) / len(self.rsiz)
        cross_sum = sum(c[0] for c in self.crosses)

        # -- Broker saturation: cancel all open orders and close the position,
        #    then immediately place 3 new orders.  On the next bar the cycle
        #    repeats, so the broker always has pending limit/stop orders to
        #    process plus a market order to match.
        self.close()

        price = self.data.close[0]
        if score + cross_sum >= 0:
            self.buy()  # market
            self.buy(exectype=bt.Order.Limit, price=price * 0.99, size=1)  # limit
            self.buy(exectype=bt.Order.Stop, price=price * 1.01, size=1)  # stop
        else:
            self.sell()  # market
            self.sell(exectype=bt.Order.Limit, price=price * 1.01, size=1)  # limit
            self.sell(exectype=bt.Order.Stop, price=price * 0.99, size=1)  # stop

    # ── Pre-broker execution (cheat_on_open section) ─────────────────────────

    def next_open(self):
        """
        Called before the broker on each bar when cheat_on_open=True.
        Iterates SMAs to produce genuine work and places a market order so
        the cheat_on_open section records meaningful timing data.
        """
        _ = sum(s[0] for s in self.smas)
        self.close()
        self.buy(size=1)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    datadir = os.path.abspath(os.path.join(modpath, "../../datas"))

    out_dir = os.environ.get("BT_OUTPUT_DIR", os.getcwd())
    os.makedirs(out_dir, exist_ok=True)

    sections_file = os.path.join(out_dir, "energy_sections.csv")
    os.makedirs(os.path.dirname(sections_file), exist_ok=True)
    with open(sections_file, "w") as f:
        pass    
    # Data files available in the datas/ directory that cover 1999–2014
    feeds_config = [
        ("orcl-1995-2014.txt", "ORCL"),
        ("nvda-1999-2014.txt", "NVDA"),
        ("yhoo-1996-2014.txt", "YHOO"),
    ]

    tracker = codecarbon.EmissionsTracker(
        measure_power_secs=1,
        log_level="error",
        save_to_file=False,
    )
    tracker.start()
    task_results = []

    for run in range(1, N_RUNS + 1):
        print(f"\n{'='*50}")
        print(f"  Max-stress run {run}/{N_RUNS}")
        print(f"{'='*50}")

        # ── Section: backtesting_setup ────────────────────────────────────────
        tracker.start_task("backtesting_setup")
        cerebro = bt.Cerebro()

        for _ in range(10):
            cerebro.addstorecb(_noop_store_cb)
            cerebro.adddatacb(_noop_data_cb)

        cerebro.addstrategy(MaxStressStrategy)

        cerebro.broker.setcash(1_000_000.0)
        cerebro.broker.setcommission(commission=0.001)
        cerebro.broker.set_coo(True)
        task_results.append(("backtesting_setup", tracker.stop_task()))

        # ── Section: data_ingestion ───────────────────────────────────────────
        tracker.start_task("data_ingestion")
        for filename, name in feeds_config:
            data = bt.feeds.YahooFinanceCSVData(
                dataname=os.path.join(datadir, filename),
                fromdate=FROM_DATE,
                todate=TO_DATE,
                reverse=False,
            )
            cerebro.adddata(data, name=name)
            cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks, name=f"{name}_W")
            cerebro.resampledata(data, timeframe=bt.TimeFrame.Months, name=f"{name}_M")
        task_results.append(("data_ingestion", tracker.stop_task()))

        # ── Section: strategy_execution ───────────────────────────────────────
        tracker.start_task("strategy_execution")
        print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f}")
        cerebro.run(runonce=False)
        print(f"Final Portfolio Value:   {cerebro.broker.getvalue():.2f}")
        task_results.append(("strategy_execution", tracker.stop_task()))

    import csv as _csv
    with open(sections_file, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["section", "duration_s", "cpu_energy_kWh", "energy_consumed_kWh"])
        for name, t in task_results:
            w.writerow([name, round(t.duration, 6), round(t.cpu_energy, 10), round(t.energy_consumed, 10)])

    print(f"Energy data written to {sections_file} ({len(task_results)} rows)")
    
    print(f"\n{'='*50}")
    print("All runs complete. Running energy analysis...")
    print(f"{'='*50}\n")

    analysis_script = os.path.abspath(os.path.join(modpath, "analyze_energy.py"))
    summary_file = os.path.join(out_dir, "energy_summary.csv")

    subprocess.run(
        [sys.executable, analysis_script, "--sections", sections_file, "--output", summary_file],
        check=True,
    )
