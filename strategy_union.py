from Alpha1.strategy import *
from Alpha2.strategy import *
from datetime import datetime

import backtester

def process_data(raw, bar):
    price_columns = list(map(lambda symbol: symbol+"_Price", symbols))
    vol_columns = list(map(lambda symbol: symbol+"_Volume", symbols))
    prices = raw[price_columns].iloc[bar]
    vols = raw[vol_columns].iloc[bar]
    LMA = raw[price_columns].rolling(50).mean().iloc[bar]
    SMA = raw[price_columns].rolling(14).mean().iloc[bar]
    return {
        "price" : prices,
        "volume" : vols,
        "LMA" : LMA,
        "SMA" : SMA
    }

bt = backtester.Backtester(symbols, '2023-01-01', '2024-06-05', 10000000, 0.0025, process_data)
symbols = bt.symbols

bar = 0
while True:
    data, today = bt.go_next()
    if data == -1:
        break

    
    bar += 1
bt.print_result()
bt.plot_result()
    