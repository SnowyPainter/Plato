from Alpha1.strategy import *

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
    

symbols = ["MSFT", "TSLA", "AAPL", "NVDA", "AMD"]
bt = backtester.Backtester(symbols, '2023-01-01', '2024-06-05', 10000000, 0.0025, process_data)
MABT = MABreakThrough()

while True:
    data = bt.go_next()
    if data == -1:
        break
    buy_list, sell_list = MABT.action(symbols, data)
    for symbol in buy_list:
        bt.buy(symbol)
    for symbol in sell_list:
        bt.sell(symbol)
    
bt.plot_result()
    