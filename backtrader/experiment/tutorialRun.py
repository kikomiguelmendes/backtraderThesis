from __future__ import absolute_import, division, print_function, unicode_literals

"""
tutorialRun.py — Lightweight sanity-check benchmark.

Same flow as maxStressRun.py, scaled down for fast iteration:

  notifications   — 1 store callback + 1 data callback  (vs 10+10)
  data_feed       — 1 symbol (ORCL), no resampling       (vs 3 × 3 feeds)
  cheat_on_open   — set_coo(True), next_open() present   (same)
  broker          — 1 order per bar                      (vs 3)
  strategy_next   — 1 SMA + 1 EMA + 1 CrossOver          (vs 20+20+...)
"""

import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import backtrader as bt

N_RUNS = 1
FROM_DATE = datetime.datetime(2014, 12, 1)
TO_DATE = datetime.datetime(2014, 12, 31)


def _noop_store_cb(msg, *args, **kwargs):
    pass


def _noop_data_cb(data, status, *args, **kwargs):
    pass


class TutorialStrategy(bt.Strategy):
    def __init__(self):
        self.sma = bt.ind.SMA(self.data, period=10)
        self.ema = bt.ind.EMA(self.data, period=10)
        self.cross = bt.ind.CrossOver(self.sma, self.ema)

    def next(self):
        if self.cross[0] > 0:
            self.close()
            self.buy()
        elif self.cross[0] < 0:
            self.close()
            self.sell()

    def next_open(self):
        _ = self.sma[0]
        self.close()
        self.buy(size=1)


def setup_cerebro(cerebro, datadir):
    """Configure a cerebro instance for one tutorial run."""
    cerebro.addstorecb(_noop_store_cb)
    cerebro.adddatacb(_noop_data_cb)
    cerebro.addstrategy(TutorialStrategy)
    data = bt.feeds.YahooFinanceCSVData(
        dataname=os.path.join(datadir, "orcl-1995-2014.txt"),
        fromdate=FROM_DATE,
        todate=TO_DATE,
        reverse=False,
    )
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_coo(True)


if __name__ == "__main__":
    modpath = os.path.dirname(os.path.abspath(__file__))
    datadir = os.path.abspath(os.path.join(modpath, "../../datas"))

    out_dir = os.environ.get("BT_OUTPUT_DIR", os.getcwd())
    os.makedirs(out_dir, exist_ok=True)

    cerebro = bt.Cerebro(cheat_on_open=True)
    setup_cerebro(cerebro, datadir)
    print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f}")
    cerebro.run(runonce=False)
    print(f"Final Portfolio Value:   {cerebro.broker.getvalue():.2f}")
