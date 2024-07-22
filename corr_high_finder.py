import utils
from datetime import datetime, timedelta
import calendar
import Neo_invest

import json

def get_high_corr_pairs(start, end):
    pairs = []
    for key, value in utils.THEMES.items():
        stocks = list(utils.get_theme_stocks(value).keys())
        df, symbols = utils.load_historical_datas(stocks, start, end, '1h')
        df = df.filter(regex='_Price$')
        corr_matrix = df.corr()
        corr_pairs = corr_matrix.unstack()
        high_corr_pairs = corr_pairs[(corr_pairs < 1) & (corr_pairs >= 0.9)]
        high_corr_pairs = high_corr_pairs.drop_duplicates()
        high_corr_pairs = high_corr_pairs.drop_duplicates()
        high_corr_tuples = [(idx[0], idx[1]) for idx, corr in high_corr_pairs.items()]
        pairs = pairs + high_corr_tuples
    return pairs

def filter_pairs(pairs, kospi=True):
    filtered = []
    for pair in pairs:
        if kospi == True and ("KQ" in pair[0] or "KQ" in pair[1]):
            continue
        filtered.append((pair[0].replace('_Price', ''), pair[1].replace('_Price', '')))
    return filtered

def get_high_backtest_result(pairs, start, end):
    results = {}
    for pair in pairs:
        name = pair[0] + pair[1]
        neo = Neo_invest.NeoInvest(pair[0], pair[1], 1000000000)
        result = neo.backtest(start, end, print_result=False)
        results[name] = result
    
    sharp_max_key = max(results, key=lambda k: results[k]['sharp'])
    best_max_key = max(results, key=lambda k: results[k]['best'])
    worst_min_key = min(results, key=lambda k: results[k]['worst'])
    end_max_key = max(results, key=lambda k: results[k]['end'])

    print("Max Sharp : ", sharp_max_key)
    print(results[sharp_max_key])
    print("Max Best : ", best_max_key)
    print(results[best_max_key])
    print("Max Worst : ", worst_min_key)
    print(results[worst_min_key])
    print("Max End : ", end_max_key)
    print(results[end_max_key])
    
    text = f"Best Sharp : {sharp_max_key} \n"
    text += json.dumps(results[sharp_max_key], sort_keys=True, indent=4) + "\n"
    text += f"Best Return : {best_max_key} \n"
    text += json.dumps(results[best_max_key], sort_keys=True, indent=4) + "\n"
    text += f"Best End Return : {end_max_key} \n"
    text += json.dumps(results[end_max_key], sort_keys=True, indent=4) + "\n"
    text += f"Worst Return : {worst_min_key} \n"
    text += json.dumps(results[worst_min_key], sort_keys=True, indent=4) + "\n"
    
    with open("recommend stocks.txt", 'w') as f:
        f.write(text)
    
def find_stocks_to_invest():
    today = datetime.today()
    end = today.strftime('%Y-%m-%d')
    first_day_of_this_month = today.replace(day=1)
    last_month_last_day = first_day_of_this_month - timedelta(days=1)
    last_month_first_day = last_month_last_day.replace(day=1)
    start = last_month_first_day.strftime('%Y-%m-%d')

    print(f"{start} ~ {end} | Recently most co-related stocks.")

    pairs = get_high_corr_pairs(start, end)
    pairs = filter_pairs(pairs, kospi=False)
    if len(pairs) == 0:
        print("Cannot find high corr stocks in these themes.")
    else:
        get_high_backtest_result(pairs, start, end)