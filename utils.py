import pandas as pd
from bs4 import BeautifulSoup
import requests
import yfinance as yf
from scipy.stats.mstats import winsorize
import numpy as np
from datetime import datetime, timedelta
import pytz

def merge_dfs(dfs):
    merged = dfs[0]
    for i in range(1, len(dfs)):
        merged = merged.join(dfs[i])
    return merged

def today(tz = 'Asia/Seoul'):
        return datetime.now(pytz.timezone(tz))
def today_before(day, tz = 'Asia/Seoul'):
    return datetime.now(pytz.timezone(tz)) - timedelta(days=day)

def today_and_month_ago():
    today = datetime.today()
    end = today.strftime('%Y-%m-%d')
    first_day_of_this_month = today.replace(day=1)
    last_month_last_day = first_day_of_this_month - timedelta(days=1)
    last_month_first_day = last_month_last_day.replace(day=1)
    start = last_month_first_day.strftime('%Y-%m-%d')
    return start, end

import os
    
def create_params_dir():
    if not os.path.isdir('./model_params'):
        os.makedirs('./model_params')

THEMES = {
    "반도체" : {
        "HBM" : 536,
        "뉴로모픽" : 556,
    },
    "건설" : {
        "원자력 발전" : 205,
        "우크라이나 재건" : 517,
    },
    "조선" : {
        "조선" : 30,
    },
    "방산" : {
        "우주항공과국방" : 284,
        "전쟁" : 144
    }
}

def get_theme_stocks(theme_no):
    text = requests.get(f"https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={theme_no}").text
    soup = BeautifulSoup(text, "html.parser")
    result = {}
    stocks = soup.find_all("td", {"class":"name"})
    for stock in stocks:
        code = (stock.find('a').get('href')).replace('/item/main.naver?code=', '')
        name = stock.get_text().split(' *')[0]
        if "*" in stock.get_text():
            code += ".KQ"
        else:
            code += ".KS"
        result[code] = name
    return result

def get_all_stock_datas_in_theme():
    all_stocks = []
    for theme, no in THEMES.items():
        all_stocks = all_stocks + list(get_theme_stocks(no).keys())
    return list(set(all_stocks))

def load_historical_data(symbol, start, end, interval='1d'):
    d = yf.download(symbol, start=start, end=end, interval=interval)
    d.rename(columns={'Open': symbol+'_Price', 'Volume' : symbol+"_Volume", 'High' : symbol+"_High", 'Low' : symbol+"_Low"}, inplace=True)
    d.index = pd.to_datetime(d.index, format="%Y-%m-%d %H:%M:%S%z")
    return d[[symbol+'_Price', symbol+"_Volume", symbol+"_High", symbol+"_Low"]]

def load_historical_datas(symbols, start, end, interval='1d'):
    dfs = []
    edit_symbols = symbols.copy()
    for symbol in symbols:
        df = load_historical_data(symbol, start, end, interval)
        if df.empty == True:
            edit_symbols.remove(symbol)
            continue
        dfs.append(df)
    
    merged = merge_dfs(dfs)
    merged.dropna(inplace=True)
    
    return merged, edit_symbols

def normalize(df):
    range_val = df.max() - df.min()
    range_val[range_val == 0] = 1
    return (df - df.min()) / (range_val)

def series_winsorize(series, limits=(0.05, 0.05)):
    return winsorize(series, limits=limits)

def calculate_rsi(df, column, period=84):
    delta = df[column].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rs = rs.replace([np.inf, -np.inf], np.nan).fillna(0)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def trim_units_minmax(units):
    if units > 1:
        units = 1
    elif units < -1:
        units = -1
    return units

def df_lags(df, column, lag):
    return df[column].shift(lag)

def df_MACD(df, column, span1 = 30, span2 = 55):
    return df[column].ewm(span=span1, adjust=False).mean() - df[column].ewm(span=span2, adjust=False).mean()

def df_ADX(df, column, period = 30):
    df[column+'_TR'] = np.maximum(df[column+"_High"] - df[column+"_Low"], np.maximum(abs(df[column+"_High"] - df[column+"_Price"].shift(1)), abs(df[column+"_Low"] - df[column+"_Price"].shift(1))))
    df[column+'_+DM'] = np.where((df[column+"_High"] - df[column+"_High"].shift(1)) > (df[column+'_Low'].shift(1) - df[column+"_Low"]), 
                        np.maximum(df[column+"_High"] - df[column+"_High"].shift(1), 0), 0)
    df[column+'_-DM'] = np.where((df[column+'_Low'].shift(1) - df[column+'_Low']) > (df[column+"_High"] - df[column+"_High"].shift(1)), 
                        np.maximum(df[column+'_Low'].shift(1) - df[column+'_Low'], 0), 0)
    df[column+'_ATR'] = df[column+'_TR'].rolling(window=period).mean()
    df[column+'_+DI'] = 100 * (df[column+'_+DM'].rolling(window=period).mean() / df[column+'_ATR'])
    df[column+'_-DI'] = 100 * (df[column+'_-DM'].rolling(window=period).mean() / df[column+'_ATR'])
    df[column+'_DX'] = 100 * abs(df[column+'_+DI'] - df[column+'_-DI']) / (df[column+'_+DI'] + df[column+'_-DI'])
    return df[column+'_DX'].rolling(window=period).mean()

def process_weights(buy_weights):
    cut_dict={key:min(value, 1) for key,value in buy_weights.items()}
    total = sum(cut_dict.values())
    for key, weight in cut_dict.items():
        if total > weight:
            buy_weights[key] = weight / total
        else:
            buy_weights[key] = weight
    return buy_weights

def calculate_sale_percentage(current_percentage, target_percentage):
    sale_percentage = current_percentage - target_percentage
    return sale_percentage

def get_pct_changes(returns):
    return pd.Series(returns).pct_change().dropna()