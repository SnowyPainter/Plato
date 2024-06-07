import pandas as pd
from bs4 import BeautifulSoup
import requests
import yfinance as yf

def merge_dfs(dfs):
    merged = dfs[0]
    for i in range(1, len(dfs)):
        merged = merged.join(dfs[i])
    return merged

THEMES = {
    "HBM" : 536,
    "2차전지" : 446,
    "뉴로모픽" : 556,
    "해운" : 36
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

def load_historical_data(symbol, start, end):
    d = yf.download(symbol, start=start, end=end)
    d.rename(columns={'Open': symbol+'_Price', 'Volume' : symbol+"_Volume"}, inplace=True)
    d.index = pd.to_datetime(d.index, format="%Y-%m-%d %H:%M:%S%z")
    return d[[symbol+'_Price', symbol+"_Volume"]]

def load_historical_datas(symbols, start, end):
    dfs = []
    edit_symbols = symbols.copy()
    for symbol in symbols:
        df = load_historical_data(symbol, start, end)
        if df.empty == True:
            edit_symbols.remove(symbol)
            continue
        dfs.append(df)
    return merge_dfs(dfs), edit_symbols