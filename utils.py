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

THEMES = {
    "HBM" : 536,
    "뉴로모픽" : 556
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
    d.rename(columns={'Open': symbol+'_Price', 'Volume' : symbol+"_Volume"}, inplace=True)
    d.index = pd.to_datetime(d.index, format="%Y-%m-%d %H:%M:%S%z")
    return d[[symbol+'_Price', symbol+"_Volume"]]

def load_historical_datas(symbols, start, end, interval='1d'):
    dfs = []
    edit_symbols = symbols.copy()
    for symbol in symbols:
        df = load_historical_data(symbol, start, end, interval)
        if df.empty == True:
            edit_symbols.remove(symbol)
            continue
        dfs.append(df)
    return merge_dfs(dfs), edit_symbols

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

def df_MACD(df, column):
    return df[column].ewm(span=80, adjust=False).mean() - df[column].ewm(span=150, adjust=False).mean()

def determine_trend(df, column):
    # 1 up, 0 down
    trend = []
    for i in range(1, len(df)):
        price = df[column].iloc[i]
        price_lag = df[column].iloc[i-1]
        diff = price - price_lag
        if diff > 0.2:
            trend.append(3)
        elif diff > 0:
            trend.append(2)
        elif diff > -0.15:
            trend.append(1)
        elif diff > -0.2:
            trend.append(0)
        else:
            trend.append(-1)
    trend.insert(0, 0)
    return trend

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