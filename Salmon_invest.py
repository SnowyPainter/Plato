from Investment import kis
from Alpha1.strategy import *
from Alpha3.strategy import *
import utils

import itertools
import pandas as pd
import pytz
import math
import schedule
from datetime import datetime, timedelta
import time

def today(tz = 'Asia/Seoul'):
    return datetime.now(pytz.timezone(tz))
def today_before(day, tz = 'Asia/Seoul'):
    return datetime.now(pytz.timezone(tz)) - timedelta(days=day)

def current_prices(symbols):
    df = {}
    for symbol in symbols:
        code = symbol.split('.')[0]
        df[symbol+"_Price"] = client.get_price(code)
    df = pd.DataFrame(df, index=[datetime.now()])
    return df

def process_data(raw, norm_raw, bar):
    price_columns = list(map(lambda symbol: symbol+"_Price", symbols))
    LMA = norm_raw[price_columns].rolling(50).mean().iloc[bar]
    SMA = norm_raw[price_columns].rolling(14).mean().iloc[bar]
    return {
        "norm_price" : norm_raw[price_columns].iloc[bar],
        "price" : raw[price_columns].iloc[bar],
        "LMA" : LMA,
        "SMA" : SMA
    }

def append_current_data(raw_data, symbols):
    df = current_prices(symbols)
    raw_data = pd.concat([raw_data, df])
    return raw_data, process_data(raw_data, utils.normalize(raw_data), -1)

def action(data, symbols, MABT_weight, SP_weight, MABT_strategy, SP_strategy):
    trade_dict = {}
    for symbol in symbols:
        trade_dict[symbol] = 0
            
    buy_list, sell_list = MABT_strategy.action(symbols, data)
    for stock in buy_list:
        trade_dict[stock] += 1 * MABT_weight
    for stock in sell_list:
        trade_dict[stock] -= 1 * MABT_weight
        
    for pair in list(itertools.combinations(symbols, 2)):
        buy_list, sell_list = SP_strategy.action(data, pair[0], pair[1])
        for stock in buy_list:
            trade_dict[stock] += 1 * SP_weight
        for stock in sell_list:
            trade_dict[stock] -= 1 * SP_weight

    for stock, amount in trade_dict.items():
        units = math.floor(abs(amount))
        code = stock.split('.')[0]
        if amount > 0:
            client.buy(code, data["price"][stock+"_Price"], 0.1 * units)
        elif amount < 0:
            client.sell(code, data["price"][stock+"_Price"], 0.1 * units)

interval = '1h'
MABT_weight = 2
SP_weight = 1.5

symbols = ["042700.KS", "000660.KS", "005930.KS"]
raw_data, symbols = utils.load_historical_datas(symbols, today_before(30), today(), interval)
raw_data.index = pd.to_datetime(raw_data.index).tz_localize(None)
raw_data.drop(columns=[col for col in raw_data.columns if col.endswith('_Volume')], inplace=True)

client = kis.KISClient("MASP Sk Samsung Hanmi")
MABT = MABreakThrough()
SP = StockPair()

def schedule_job(symbols, MABT_weight, SP_weight, MABT_strategy, SP_strategy):
    global raw_data
    raw_data, processed_data = append_current_data(raw_data, symbols)
    action(processed_data, symbols, MABT_weight, SP_weight, MABT_strategy, SP_strategy)

print("Running for ", symbols, " with MASP strategy.")
while True:
    if client.is_market_open():
        schedule.every(1).hour.do(schedule_job, symbols, MABT_weight, SP_weight, MABT, SP)
        while client.is_market_open():
            schedule.run_pending()
            time.sleep(1)
        schedule.clear()
        print("Market is Closed")
    time.sleep(60)