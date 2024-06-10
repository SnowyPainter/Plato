
from datetime import datetime

import itertools
import backtester

def process_data(raw, norm_raw, bar):
    price_columns = list(map(lambda symbol: symbol+"_Price", symbols))
    vol_columns = list(map(lambda symbol: symbol+"_Volume", symbols))
    prices = raw[price_columns].iloc[bar]
    vols = raw[vol_columns].iloc[bar]
    return {
        "norm_price" : norm_raw[price_columns].iloc[bar],
        "price" : prices,
    }

#한미반도체, SK하이닉스, 삼성전자
symbols = ["042700.KS", "000660.KS", "005930.KS"]


bt = backtester.Backtester(symbols, '2023-01-01', '2024-01-01', '1d', 10000000, 0.0025, process_data)
symbols = bt.symbols

bar = 0

while True:
    data, today = bt.go_next()
    if data == -1:
        break
    
    bar += 1
bt.print_result()
bt.plot_result()
    