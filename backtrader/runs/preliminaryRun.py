from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import sys
import os
import time
import subprocess
import codecarbon

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import backtrader as bt

N_RUNS = 30
COOLDOWN_S = 60
FROM_DATE = datetime.datetime(1999, 1, 1)
TO_DATE = datetime.datetime(2014, 12, 31)


def _noop_store_cb(msg, *args, **kwargs):
    pass


def _noop_data_cb(data, status, *args, **kwargs):
    pass

class MaxStressStrategy(bt.Strategy):

    def __init__(self):
        d = self.data

        sma_periods = range(5, 205, 10)
        ema_periods = range(5, 205, 10)
        self.smas = [bt.ind.SMA(d, period=p) for p in sma_periods]
        self.emas = [bt.ind.EMA(d, period=p) for p in ema_periods]

        rsi_periods = range(5, 55, 5)
        self.rsiz = [bt.ind.RSI(d, period=p) for p in rsi_periods]

        self.macds = [bt.ind.MACD(d) for _ in range(5)]

        bb_periods = range(10, 60, 10)
        self.bbs = [bt.ind.BollingerBands(d, period=p) for p in bb_periods]

        atr_periods = range(5, 30, 5)
        self.atrs = [bt.ind.ATR(d, period=p) for p in atr_periods]

        self.stochs = [bt.ind.Stochastic(d) for _ in range(5)]

        self.crosses = [
            bt.ind.CrossOver(s, e) for s, e in zip(self.smas[:10], self.emas[:10])
        ]

    def next(self):
        score = sum(s[0] - e[0] for s, e in zip(self.smas, self.emas))
        cross_sum = sum(c[0] for c in self.crosses)

        self.close()

        price = self.data.close[0]
        if score + cross_sum >= 0:
            self.buy()
            self.buy(exectype=bt.Order.Limit, price=price * 0.99, size=1)
            self.buy(exectype=bt.Order.Stop, price=price * 1.01, size=1)
        else:
            self.sell()
            self.sell(exectype=bt.Order.Limit, price=price * 1.01, size=1)
            self.sell(exectype=bt.Order.Stop, price=price * 0.99, size=1)

    def next_open(self):
        _ = sum(s[0] for s in self.smas)
        self.close()
        self.buy(size=1)


if __name__ == "__main__":
    modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    datadir = os.path.abspath(os.path.join(modpath, "../../datas"))

    out_dir = os.environ.get("BT_OUTPUT_DIR", os.getcwd())
    os.makedirs(out_dir, exist_ok=True)

    sections_file = os.path.join(out_dir, "energy_sections.csv")
    os.makedirs(os.path.dirname(sections_file), exist_ok=True)
    with open(sections_file, "w") as f:
        pass

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

        tracker.start_task("backtesting_setup")
        cerebro = bt.Cerebro(cheat_on_open=True)

        for _ in range(10):
            cerebro.addstorecb(_noop_store_cb)
            cerebro.adddatacb(_noop_data_cb)

        cerebro.addstrategy(MaxStressStrategy)

        cerebro.broker.setcash(1_000_000.0)
        cerebro.broker.setcommission(commission=0.001)
        task_results.append(("backtesting_setup", tracker.stop_task()))

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

        tracker.start_task("strategy_execution")
        print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f}")
        cerebro.run(runonce=False)
        print(f"Final Portfolio Value:   {cerebro.broker.getvalue():.2f}")
        task_results.append(("strategy_execution", tracker.stop_task()))

        if run < N_RUNS:
            print(f"  Cooling down for {COOLDOWN_S}s...")
            time.sleep(COOLDOWN_S)

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
