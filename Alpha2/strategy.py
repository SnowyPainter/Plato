import sys
sys.path.append('..')
import utils
import pytz
from datetime import datetime, timedelta, time
import numpy as np
import math

tz = "Asia/Seoul"

# RUN BEFORE MARKET OPENS
class ThemeCapture:
    def explore_themes(self, start, end):
        dfs = {}
        the_stocks = {}
        for key, value in utils.THEMES.items():
            stocks = list(utils.get_theme_stocks(value).keys())
            df, symbols = utils.load_historical_datas(stocks, start, end, '1h')
            for column in list(map(lambda symbol: symbol+"_Price", symbols)):
                df[column+"_LR"] = np.log(df[column] / df[column].shift(1))
            dfs[key] = df
            the_stocks[key] = symbols
        return dfs, the_stocks
    
    def calculate_most_stable(self, dfs, stocks_by_theme):
        profit_sums = {}
        for key, df in dfs.items():
            profit_sum = 0
            for stock in stocks_by_theme[key]:
                column = stock + "_Price_LR"
                profit_sum += df[column].iloc[-1]
            profit_sum /= len(stocks_by_theme[key])
            profit_sums[key] = profit_sum
        return max(profit_sums, key=profit_sums.get)
    
    def calculate_most_profitable(self, dfs, stocks_by_theme):
        #계산식
        #Log Return 상위 50% 종목들의 Log return 합이 가장 큰 것
        log_returns = []
        themes = []
        for key, df in dfs.items():
            lrs = []
            for stock in stocks_by_theme[key]:
                column = stock + "_Price_LR"
                lrs.append(df[column].iloc[-1])
            lrs.sort()
            log_returns.append(sum(lrs[:math.floor(len(lrs)/2)]))
            themes.append(key)
        return themes[log_returns.index(max(log_returns))]
    
    def action(self, day_crit):
        dfs, stocks_by_theme = self.explore_themes((day_crit - timedelta(days=5)).strftime("%Y-%m-%d"), day_crit.strftime("%Y-%m-%d"))
        stable_theme = self.calculate_most_stable(dfs, stocks_by_theme)
        profit_theme = self.calculate_most_profitable(dfs, stocks_by_theme)
        stable_stocks = stocks_by_theme[stable_theme]
        profit_theme = stocks_by_theme[profit_theme]
        buy_list = list(set(stable_stocks).intersection(profit_theme))
        return buy_list
            