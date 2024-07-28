import time
import schedule
from datetime import datetime
import os, re
import multiprocessing as mp

import Neo_invest
import corr_high_finder
import utils
import connect_tester

i = input("Continue to Check Connection?(yes/no) : ")
if i == 'yes':
    connect_tester.check_connection()

def get_symbols(option):
    print(f"{option} 선택됨. 심볼 2개를 입력하세요:")
    symbols = []
    for i in range(2):
        symbol = input(f"심볼 {i + 1}: ")
        symbols.append(symbol)
    return symbols

def get_bt_term(option):
    print(f"{option} 선택됨")
    start = input(f"시작 날짜를 입력하세요(20xx-xx-xx) : ")
    end = input(f"종료 날짜를 입력하세요(20xx-xx-xx) : ")
    return start, end

def get_amounts(option):
    print(f"{option} 선택됨.")
    max_operate_amount = input("최대 운용 가능 금액을 입력하세요 : ")
    return float(max_operate_amount)

invester = None
hour_divided_time = 1
options = ['백테스팅', '실전 투자', '종목 추천']

if __name__ == '__main__':
    while True:
        i = 1
        for option in options:
            print(f"{i} : {option}")
            i += 1
        opt = input("Option : ")
        
        if opt == "1":
            selected_option = "Backtest"
            symbols = get_symbols(selected_option)
            start, end = get_bt_term(selected_option)
            print(f"심볼 : {', '.join(symbols)}")
            print(f"기간 : {start} ~ {end}")
            invester = Neo_invest.NeoInvest(symbols[0], symbols[1], 10000000000)
            invester.backtest(start, end)
        elif "2" in opt:
            selected_option = "Invest"
            symbols = get_symbols(selected_option)
            cash, max_operate_amount = get_amounts(selected_option)
            exists_params = input("학습한 Parameter가 존재합니까?(yes/no) : ")
            if exists_params == 'yes':
                orders = utils.get_saved_orders(symbols)
            else:
                orders = {}
            invester = Neo_invest.NeoInvest(symbols[0], symbols[1], max_operate_amount, orders)
            
            interval = '30m'
            if not ("skip" in opt):
                start, end = utils.today_and_month_ago()
                h1_result = invester.backtest(start, end, '1h', False)
                m30_result = invester.backtest(start, end, '30m', False)
                
                end_diff = abs(h1_result['end'] - m30_result['end'])
                if end_diff <= 0.02:
                    if h1_result['sharp'] > m30_result['sharp']:
                        interval = '1h'
                    else:
                        interval = '30m'
                else:
                    interval = '1h' if h1_result['end'] > m30_result['end'] else '30m'
            
            def action():
                global invester, interval
                hdt = 1 if interval == '1h' else 2
                invester.append_current_data()
                invester.action(hour_divided_time=hdt)
            
            print(f"{', '.join(symbols)}에 관해서 OU+TP Strategy를 {interval} 마다 가동합니다.")
            
            if interval == '1h':
                for hour in range(9, 16):
                    schedule.every().day.at(f"{hour:02d}:01").do(action)
            elif interval == '30m':
                for hour in range(9, 16):
                    schedule.every().day.at(f"{hour:02d}:00").do(action)
                    schedule.every().day.at(f"{hour:02d}:29").do(action)
            while True:
                schedule.run_pending()
                time.sleep(1)
        elif opt == "3":
            processes = []
            result_batch = []
            for theme_name, theme in utils.THEMES.items():
                pairs = corr_high_finder.find_stocks_to_invest(theme)
                if len(pairs) == 0:
                    continue
                manager = mp.Manager()
                results = manager.dict()
                result_batch.append(results)
                start, end = utils.today_and_month_ago()
                
                for pair in pairs:
                    p = mp.Process(target=corr_high_finder.run_backtest, args=(pair, start, end, results))
                    processes.append(p)
                    p.start()
                for p in processes:
                    p.join()
                corr_high_finder.save_results(results, theme_name)