from Alpha1.strategy import *
from Alpha3.strategy import *

import ini_reader
from datetime import datetime
import math
import itertools
import backtester

def process_data(raw, norm_raw, bar):
    price_columns = list(map(lambda symbol: symbol+"_Price", symbols))
    prices = raw[price_columns].iloc[bar]
    LMA = norm_raw[price_columns].rolling(50).mean().iloc[bar]
    SMA = norm_raw[price_columns].rolling(14).mean().iloc[bar]
    return {
        "norm_price" : norm_raw[price_columns].iloc[bar],
        "price" : prices,
        "LMA" : LMA,
        "SMA" : SMA
    }

#한미반도체, SK하이닉스, 삼성전자
symbols = ["042700.KS", "000660.KS", "005930.KS"]
symbols = input("종목 코드를 일렬로 입력(예: 042700.KS 000660.KS 005930.KS) : ").split(" ")
config = ini_reader.strategy_settings_MASP("./settings/MASP.ini")

bt = backtester.Backtester(symbols, config["START_DATE"], config["END_DATE"], config["INTERVAL"], config["AMOUNT"], 0.0025, process_data)
symbols = bt.symbols

MABT = MABreakThrough()
SP = StockPair()

MABT_weight = config["MABT_W"]
SP_weight = config["SP_W"]

bar = 0

while True:
    trade_dict = {}
    for symbol in symbols:
        trade_dict[symbol] = 0
    
    data, today = bt.go_next()
    if data == -1:
        break
    
    buy_list, sell_list = MABT.action(symbols, data)
    for stock in buy_list:
        trade_dict[stock] += 1 * MABT_weight
    for stock in sell_list:
        trade_dict[stock] -= 1 * MABT_weight
    
    for pair in list(itertools.combinations(symbols, 2)):
        buy_list, sell_list = SP.action(data, pair[0], pair[1])
        for stock in buy_list:
            trade_dict[stock] += 1 * SP_weight
        for stock in sell_list:
            trade_dict[stock] -= 1 * SP_weight
    
    for stock, amount in trade_dict.items():
        units = math.floor(abs(amount))
        if amount > 0:
            bt.buy(stock, 0.1 * units)
        elif amount < 0:
            bt.sell(stock, 0.1 * units)
    
    bar += 1
bt.print_result()
bt.plot_result()
    