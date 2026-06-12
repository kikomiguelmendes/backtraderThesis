from __future__ import absolute_import, division, print_function, unicode_literals

"""
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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import backtrader as bt

N_RUNS = 30
FROM_DATE = datetime.datetime(1999, 1, 1)  # earliest date shared by all 3 feeds
TO_DATE = datetime.datetime(2014, 12, 31)

FEEDS_CONFIG = [
    ("orcl-1995-2014.txt", "ORCL"),
    ("nvda-1999-2014.txt", "NVDA"),
    ("yhoo-1996-2014.txt", "YHOO"),
]

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

def setup_cerebro(cerebro, datadir):
    """Configure a cerebro instance for one max-stress run."""
    for _ in range(10):
        cerebro.addstorecb(_noop_store_cb)
        cerebro.adddatacb(_noop_data_cb)

    cerebro.addstrategy(MaxStressStrategy)

    for filename, name in FEEDS_CONFIG:
        data = bt.feeds.YahooFinanceCSVData(
            dataname=os.path.join(datadir, filename),
            fromdate=FROM_DATE,
            todate=TO_DATE,
            reverse=False,
        )
        cerebro.adddata(data, name=name)
        cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks, name=f"{name}_W")
        cerebro.resampledata(data, timeframe=bt.TimeFrame.Months, name=f"{name}_M")

    cerebro.broker.setcash(1_000_000.0)
    cerebro.broker.setcommission(commission=0.001)

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
