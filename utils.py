import pandas as pd
from bs4 import BeautifulSoup
import requests
import yfinance as yf
from scipy.stats.mstats import winsorize
import numpy as np
from datetime import datetime, timedelta
import pytz
import os, re

from Models import MC_VaR

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

def is_valid_date_format(date_str):
    pattern = r'^20\d{2}-\d{2}-\d{2}$'
    return re.match(pattern, date_str) is not None

def start_end_date_valid(start, end):
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y-%m-%d")
    return start_date < end_date

def create_params_dir():
    if not os.path.isdir('./model_params'):
        os.makedirs('./model_params')

def get_order(filename):
    with open(filename, 'r') as file:
        content = file.read().strip()
        match = re.match(r'\((\d+), (\d+), (\d+)\)', content)
        if match:
            p, d, q = map(int, match.groups())
            return (p, d, q)
        else:
            print(f"파일 {filename}의 내용이 예상된 형식이 아닙니다.")
            return (3, 1, 3)

def get_saved_orders(symbols):
    orders = {}
    for filename in os.listdir('./model_params'):
        for symbol in symbols:
            if filename == f"{symbol} ARIMA order.txt":
                fname = os.path.join('./model_params', filename)
                orders[symbol] = get_order(fname)
    
    #완전성 검사
    flag = False
    for symbol in symbols:
        if not (symbol in orders):
            flag = True
    if flag:
        return {}
    return orders

def korean_currency_format(amount):
    return format(amount, ',')

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

def load_market_index(market='^KS11', interval='30m'):
    return np.array(load_historical_data(market, today_before(1), today(), interval)[market+"_Price"])

def coef(y):
    x = np.arange(len(y))
    coefficients = np.polyfit(x, y, 1)
    return coefficients[0]

def nplog(df):
    data_log = df.apply(lambda x: np.log(x + 1))
    return data_log

def normalize(df):
    range_val = df.max() - df.min()
    range_val[range_val == 0] = 1
    return (df - df.min()) / (range_val)

def get_bt_result(portfolio_returns, evlus, init_amount):
    VaR = MC_VaR.get_historical_VaR2(evlus, init_amount, 30)
    end_return = portfolio_returns[-1]
    worst_return = min(portfolio_returns)
    best_return = max(portfolio_returns)
    mean_return = np.mean(portfolio_returns)
    std_return = np.std(portfolio_returns)
    sharp_ratio = mean_return / std_return
    return end_return, best_return, worst_return, sharp_ratio, VaR

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

def preprocess_weights(buy_weights, cash=1, limit=1):
    cut_dict={key:min(value, 1) for key,value in buy_weights.items()}
    total = sum(cut_dict.values())
    for key, weight in cut_dict.items():
        if total > weight:
            buy_weights[key] = weight / total
        else:
            buy_weights[key] = weight
    if cash < 0:
        cash = 0
    
    for s, w in buy_weights.items():
        w = buy_weights[s] * (cash/limit)
        if w < 0.1:
            break
        else:
            buy_weights[s] = w
    return buy_weights

def calculate_sale_percentage(current_percentage, target_percentage):
    sale_percentage = current_percentage - target_percentage
    return sale_percentage

def get_pct_changes(returns):
    return pd.Series(returns).pct_change().dropna()

def calculate_fee(amount):
    if amount < 500000:
        fee = amount * 0.004971487
    elif 500000 <= amount < 3000000:
        fee = amount * 0.001271487 + 2000
    elif 3000000 <= amount < 30000000:
        fee = amount * 0.001271487 + 1500
    else:
        fee = amount * 0.001171487
    return fee * 2

def calculate_stock_increase_p(qty, avgp, curr_pr):
    fee = calculate_fee(qty * avgp)
    net = curr_pr - fee
    return (net_profit - avgp) / avgp