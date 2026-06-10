from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import backtrader as bt

FROM_DATE = datetime.datetime(1999, 1, 1)
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
    def __init__(self):
        d = self.data

        self.smas = [bt.ind.SMA(d, period=p) for p in range(5, 205, 10)]
        self.emas = [bt.ind.EMA(d, period=p) for p in range(5, 205, 10)]
        self.rsiz = [bt.ind.RSI(d, period=p) for p in range(5, 55, 5)]
        self.macds = [bt.ind.MACD(d) for _ in range(5)]
        self.bbs = [bt.ind.BollingerBands(d, period=p) for p in range(10, 60, 10)]
        self.atrs = [bt.ind.ATR(d, period=p) for p in range(5, 30, 5)]
        self.stochs = [bt.ind.Stochastic(d) for _ in range(5)]
        self.crosses = [
            bt.ind.CrossOver(s, e) for s, e in zip(self.smas[:10], self.emas[:10])
        ]
        self.portfolio_values = []

    def next(self):
        score = sum(s[0] - e[0] for s, e in zip(self.smas, self.emas))
        cross_sum = sum(c[0] for c in self.crosses)

        self.portfolio_values.append(self.broker.get_value())

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

    cerebro = bt.Cerebro(cheat_on_open=True)

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

    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    results = cerebro.run(runonce=False)
    strategy = results[0]
    print("Final Portfolio Value:   %.2f" % cerebro.broker.getvalue())

    output_path = os.path.join(modpath, "baseline.json")
    with open(output_path, "w") as f:
        json.dump(strategy.portfolio_values, f)
    print(f"Portfolio values saved to {output_path}")