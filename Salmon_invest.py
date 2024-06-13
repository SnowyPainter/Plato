from Investment import kis
from Alpha1.strategy import *
from Alpha3.strategy import *
import utils
from Models import model

import itertools
import pandas as pd
import pytz
import math
import schedule
from datetime import datetime, timedelta
import time
import sys

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

def action(trend_predictors, data, symbols, MABT_weight, SP_weight, TREND_BASIS, MABT_strategy, SP_strategy):
    red_flags = []
    trade_dict = {}
    basis = {}
    for symbol in symbols:
        trade_dict[symbol] = 0
        d = data[0][[symbol+"_Price"]].iloc[-trend_predictors[symbol].minimal_data_length-1:-1]
        trend = trend_predictors[symbol].predict(d, symbol)
        basis[symbol] = trend * 0.3 * TREND_BASIS
        
    buy_list, sell_list = MABT_strategy.action(symbols, data[1])
    for stock in buy_list:
        trade_dict[stock] += 1 * MABT_weight
    for stock in sell_list:
        trade_dict[stock] -= 1 * MABT_weight
    
    for pair in list(itertools.combinations(symbols, 2)):
        buy_list, sell_list = SP_strategy.action(data[1], pair[0], pair[1])
        for stock in buy_list:
            trade_dict[stock] += 1 * SP_weight
        for stock in sell_list:
            trade_dict[stock] -= 1 * SP_weight

    for stock, amount in trade_dict.items():
        units = math.floor(abs(amount))
        ratio = 0.1 * (units + basis[stock])
        if stock in red_flags:
            continue
        code = stock.split('.')[0]
        if amount > 0:
            print(f'buy {stock} {ratio}')
            client.buy(code, data[1]["price"][stock+"_Price"], ratio)
        elif amount < 0:
            print(f'sell {stock} {ratio}')
            client.sell(code, data[1]["price"][stock+"_Price"], ratio)

start, end, interval = today_before(30), today(), '1h'
symbols = ["042700.KS", "000660.KS", "005930.KS"]
MABT_weight = 2
SP_weight = 1.5
TREND_BASIS = 2.5
trend_predictors = {}

raw_data, symbols = utils.load_historical_datas(symbols, start, end, interval)
raw_data.index = pd.to_datetime(raw_data.index).tz_localize(None)
raw_data.drop(columns=[col for col in raw_data.columns if col.endswith('_Volume')], inplace=True)

for symbol in symbols:
    trend_predictors[symbol] = model.TrendPredictor(symbol, start, end, interval)
    print(trend_predictors[symbol].fit())
    
client = kis.KISClient("Salmon Sk Samsung Hanmi")
MABT = MABreakThrough()
SP = StockPair()

raw_data, processed_data = append_current_data(raw_data, symbols)

def schedule_job(trend_predictors, symbols, MABT_strategy, SP_strategy):
    global raw_data, MABT_weight, SP_weight, TREND_BASIS
    raw_data, processed_data = append_current_data(raw_data, symbols)
    action(trend_predictors, (raw_data, processed_data), symbols, MABT_weight, SP_weight, TREND_BASIS, MABT_strategy, SP_strategy)

schedule_job(trend_predictors, symbols, MABT, SP)

print("Running for ", symbols, " with Salmon strategy.")
while True:
    if client.is_market_open():
        schedule.every(1).hour.do(schedule_job, trend_predictors, symbols, MABT, SP)
        while client.is_market_open():
            schedule.run_pending()
            time.sleep(1)
        schedule.clear()
        print("Market is Closed")
    time.sleep(60)