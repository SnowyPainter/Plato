import sys
from PyQt5.QtWidgets import QCheckBox,QLineEdit, QMenu, QWidgetAction, QAction, QApplication, QMainWindow, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QComboBox, QLineEdit, QMessageBox, QInputDialog, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSlot, pyqtSignal
import multiprocessing as mp
import os
import configparser
import math
import pandas as pd
import json

from Strategy import Neo_invest, Compound_invest
from UI import InvestThread, Presets
from LM import news
from Models import MC_VaR, CAPM
from Investment import kis
import corr_high_finder
import utils
import connect_tester

class TradingApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.news_reader = None
        
        self.setWindowTitle("Pair Trader")
        self.setGeometry(100, 100, 400, 300)
        self.setFixedSize(1024, 680)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.body = QHBoxLayout()
        self.act_layout = QVBoxLayout()
        self.etc_layout = QVBoxLayout()
        self.opt_layout = QHBoxLayout()
        self.text_layout = QHBoxLayout()
        self.bt_layout = QVBoxLayout()
        self.invest_layout = QVBoxLayout()
        self.help_layout = QVBoxLayout()
        
        self.central_widget.setLayout(self.body)
        self.option_combo = QComboBox()
        self.options = ['Backtest', 'Invest', 'Recommend Stocks']
        self.option_combo.addItems(self.options)
        self.act_layout.addWidget(self.option_combo)

        self.add_preset_button = QPushButton("Create Preset", self)
        self.add_preset_button.clicked.connect(self.create_preset)
        self.continue_button = QPushButton("Run")
        self.continue_button.clicked.connect(self.handle_option)
        self.act_layout.addWidget(self.add_preset_button)
        self.act_layout.addWidget(self.continue_button)

        self.process_list_label = QLabel("Invest process running:")
        self.act_layout.addWidget(self.process_list_label)

        self.process_list_widget = QListWidget()
        self.process_list_widget.itemDoubleClicked.connect(self.show_process_info)
        self.process_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_list_widget.customContextMenuRequested.connect(self.show_proc_interact_menu)
        self.act_layout.addWidget(self.process_list_widget)
        
        self.refresh_token_btn = QPushButton("Refresh Token")
        self.refresh_token_btn.clicked.connect(self.refresh_token)
        self.set_api_btn = QPushButton("Set API")
        self.set_api_btn.clicked.connect(self.set_api)
        
        self.opt_layout.addWidget(self.refresh_token_btn, stretch=3)
        self.opt_layout.addWidget(self.set_api_btn, stretch=1)
        
        self.bt_result_texts = []
        self.bt_result_list = QListWidget(self)
        self.bt_result_list.itemClicked.connect(self.show_bt_result)
        self.bt_layout.addWidget(self.bt_result_list)
        
        self.invest_logs = []
        self.invest_log_list = QListWidget(self)
        self.invest_log_list.itemClicked.connect(self.show_invest_log)
        self.invest_layout.addWidget(self.invest_log_list)
        
        self.var_text = QLabel("VaR NaN", self)
        self.var_button = QPushButton("VaR", self)
        self.var_button.clicked.connect(self.calculate_VaR)
        
        self.help_layout.addWidget(self.var_text)
        self.help_layout.addWidget(self.var_button)
        
        self.etc_layout.addLayout(self.opt_layout, stretch=1)
        self.etc_layout.addLayout(self.text_layout, stretch=5)
        self.text_layout.addLayout(self.bt_layout, stretch=2)
        self.text_layout.addLayout(self.invest_layout, stretch=2)
        self.text_layout.addLayout(self.help_layout, stretch=1)
        
        self.body.addLayout(self.act_layout, stretch=1)
        self.body.addLayout(self.etc_layout, stretch=3)
        self.hour_divided_time = 1
        self.scheduled_jobs = {}
        self.processes = {}
    
    def create_preset(self):
        dialog = Presets.SavePresetDialog(self)
        dialog.exec_()
    
    def calculate_VaR(self):
        if len(self.processes) == 0:
            return
        
        VaRs = []
        initial_investment = 0
        for name, process in self.processes.items():
            initial_investment += process.invester.client.max_operate_amount
            if process.strategy == "Neo":
                vols = {}
                for symbol, vol in process.invester.volatilities.items():
                    vols[symbol] = (sum(vol) / len(vol))
                var = MC_VaR.get_MC_VaR(process.invester.client.max_operate_amount, list(vols.values()))
                VaRs.append(var)
            if process.strategy == "Compound":
                if len(process.invester.evlus) <= 1:
                    continue
                VaRs.append(MC_VaR.get_historical_VaR2(process.invester.evlus, process.invester.client.max_operate_amount, 1))

        if len(VaRs) == 0:
            return
                                
        self.var_text.setText(f"{utils.korean_currency_format(round(sum(VaRs), 2))} / {utils.korean_currency_format(initial_investment)}")
        
    def show_proc_interact_menu(self, position):
        selected_item = self.process_list_widget.itemAt(position)
        if not selected_item.text() in self.processes:
            return
        process = self.processes[selected_item.text()]

        if selected_item is not None:
            menu = QMenu()
            cancel_action = QAction('Cancel', self)
            cancel_action.triggered.connect(lambda: self.cancel_selected_process(selected_item))
            menu.addAction(cancel_action)

            update_moa = QAction('Update MOA', self)
            update_moa.triggered.connect(lambda: self.update_moa(selected_item))
            menu.addAction(update_moa)

            if process.strategy == "Neo":
                news_evlu = QAction("Current News", self)
                news_evlu.triggered.connect(lambda: self.show_news_evluate(selected_item))
                menu.addAction(news_evlu)
            
            TP_checkbox_action = QWidgetAction(self)
            self.TP_checkbox = QCheckBox('Sell TP')
            self.TP_checkbox.stateChanged.connect(self.watch_tp_checkbox_state_changed)
            self.TP_checkbox.setChecked(process.watch_TP_flag)
            TP_checkbox_action.setDefaultWidget(self.TP_checkbox)  
            menu.addAction(TP_checkbox_action)
            
            SL_checkbox_action = QWidgetAction(self)
            self.SL_checkbox = QCheckBox('Sell SL')
            self.SL_checkbox.stateChanged.connect(self.watch_sl_checkbox_state_changed)
            self.SL_checkbox.setChecked(process.watch_SL_flag)
            SL_checkbox_action.setDefaultWidget(self.SL_checkbox)
            menu.addAction(SL_checkbox_action)
            
            show_info = QAction('Info', self)
            show_info.triggered.connect(lambda: self.show_process_info(selected_item))
            menu.addAction(show_info)
            
            menu.exec_(self.process_list_widget.viewport().mapToGlobal(position))
    
    def watch_tp_checkbox_state_changed(self, state):
        item = self.process_list_widget.currentItem()
        if state == Qt.Checked:
            self.processes[item.text()].invest_info_update_signal_update(f"$WATCH_TP$&true")
        else:
            self.processes[item.text()].invest_info_update_signal_update(f"$WATCH_TP$&false")
    
    def watch_sl_checkbox_state_changed(self, state):
        item = self.process_list_widget.currentItem()
        if state == Qt.Checked:
            self.processes[item.text()].invest_info_update_signal_update(f"$WATCH_SL$&true")
        else:
            self.processes[item.text()].invest_info_update_signal_update(f"$WATCH_SL$&false")
    
    def show_process_info(self, item):
        if item is None:
            return
        
        proc = self.processes[item.text()]
        text = ''
        text += f"===== {proc.process_name} =====\n"
        text += f"{proc.invester.get_information()}"
        QMessageBox.information(self, f'{proc.process_name} Info', text)
    
    def update_moa(self, item):
        if item:
            value, ok = QInputDialog.getDouble(self, "Update MOA", "Enter Max Operate Amount:")
            if ok:
                self.processes[item.text()].invest_info_update_signal_update(f"$MOA$&{value}")
                
    def cancel_selected_process(self, item):
        if not item:
            QMessageBox.warning(self, "Warning", "You didn't select any process.")
            return
        process_name = item.text()
        if process_name in self.processes:
            self.processes[process_name].stop()
            self.processes[process_name].wait()
            del self.processes[process_name]
        self.process_list_widget.takeItem(self.process_list_widget.row(item))
        QMessageBox.information(self, "Cancel", f"{process_name} is canceled.")
    
    def update_invest_log_list(self, text):
        if "$END$" in text:
            process_name = text.split('&')[1]
            self.processes[process_name].stop()
            self.processes[process_name].wait()
            del self.processes[process_name]
            for i in range(0, self.process_list_widget.count()):
                item = self.process_list_widget.item(i)
                if item.text() == process_name:
                    self.process_list_widget.takeItem(i)
            return
        self.invest_log_list.addItem(text)
    
    def show_news_evluate(self, item):
        symbols = self.processes[item.text()].invester.symbols
        text = ''
        for symbol in symbols:
            symbol = symbol[:6]
            news_data = self.news_reader.today_only(self.news_reader.get_news_by_page(symbol, 1))
            if len(news_data) == 0:
                continue
            x = self.news_reader.preprocess_x(news_data)
            analyzed = self.news_reader.analyze(x)
            score = self.news_reader.score(analyzed)
            label = self.news_reader.label(analyzed)
            text += f"{symbol}'s Today News: {len(news_data)}\n"
            text += f"Positive: {label.count('positive')}, Neutral: {label.count('neutral')}, Negative: {label.count('negative')}\n"
            text += f"Total Score: {sum(score) :.2f}\n\n"
        
        QMessageBox.information(self, "News Evluate", text)
    
    def show_invest_log(self, item):
        index = self.invest_log_list.row(item)
        t = self.invest_logs[index]
        QMessageBox.information(self, 'Invest act', t)
    
    def show_bt_result(self, item):
        index = self.bt_result_list.row(item)
        t = self.bt_result_texts[index]
        QMessageBox.information(self, 'Backtest Result', t)

    def set_api(self):
        key, ok = QInputDialog.getText(self, "Input", f"API Key: ")
        if not ok:
            return
        secret, ok = QInputDialog.getText(self, "Input", f"API Secret: ")
        if not ok:
            return
        accno, ok = QInputDialog.getText(self, "Input", f"Account No.: ")
        if not ok:
            return
        
        config = configparser.ConfigParser()
        config['API'] = {
            'KEY': key,
            'SECRET': secret,
            'ACCNO': accno
        }
        if not os.path.exists('./settings'):
            os.mkdir('./settings')
        with open('./settings/keys.ini', 'w') as configfile:
            config.write(configfile)
        
    def refresh_token(self):
        connect_tester.check_connection()
    
    @pyqtSlot()
    def handle_option(self):
        opt = self.option_combo.currentText()
        if opt == 'Backtest':
            self.backtest()
        elif opt == 'Invest':
            self.invest()
        elif opt == 'Recommend Stocks':
            self.recommend_stocks()
        else:
            QMessageBox.warning(self, "Warning", "Not Available Option.")

    def get_bt_term(self, option):
        start, ok = QInputDialog.getText(self, "Input", f"{option} - Start(2023-xx-xx):")
        if not ok:
            return '', ''
        
        end, ok = QInputDialog.getText(self, "Input", f"{option} - End(2024-xx-xx):")
        if not ok:
            return '', ''
        
        if utils.start_end_date_valid(start, end) and utils.is_valid_date_format(start) and utils.is_valid_date_format(end):
            return start, end
        
        return '', ''

    def get_amounts(self, option):
        max_operate_amount, ok = QInputDialog.getDouble(self, "Input", f"{option} - Max Operatable Amount:")
        
        if max_operate_amount <= 0 or not ok:
            return 0
        
        return max_operate_amount
    
    def _get_preset(self):
        presets = Presets.get_presets()
        preset = {}
        if presets == []:
            QMessageBox.information(self, "Warn", "Create or Choose your invest preset.")
            return {}
        title, ok = QInputDialog.getItem(self, "Select Preset", "Choose a preset:", presets, 0, False)
        prest = {}
        if ok and title:
            with open(f"./presets/{title}.json", 'r') as f:
                preset = json.load(f)
        else:
            return {}
        return preset
    
    def _get_invester(self, symbols, client, nobacktest, only_backtest, only=''):
        if only == 'Pair Trade':
            options = ["Neo", "Compound"]
        elif only == 'Momentum':
            options = []
        else:
            options = []
        strategy, ok = QInputDialog.getItem(self, "Select Strategy", "Choose a strategy.", options, 0, False)
        invester = None, ""
        if ok and strategy:
            if strategy == "Neo":
                if self.news_reader == None:
                    self.news_reader = news.NewsReader()
                    if os.path.exists(self.news_reader.BEST_MODEL_NAME):
                        self.news_reader.load_model()
                    else:
                        QMessageBox.information(self, "Wait for a moment", "Training news model. It needs 20m.")
                        self.news_reader.train_model()
                invester = Neo_invest.NeoInvest(symbols[0], symbols[1], client, nobacktest=nobacktest, only_backtest=only_backtest)
            elif strategy == "Compound":
                invester = Compound_invest.CompoundInvest(symbols[0], symbols[1], client, nobacktest=nobacktest, only_backtest=only_backtest)
        else:
            QMessageBox.information(self, "Warn", "Select a strategy.")
            return None, ""
        return invester, strategy
    
    def backtest(self):
        
        preset = self._get_preset()
        if preset == {}:
            return
        
        symbols = preset['symbols']
        invester, invester_name = self._get_invester(symbols, None, nobacktest=False, only_backtest=True, only=preset['strategy'])

        if invester == None:
            return
        
        start, end = self.get_bt_term("Backtest")
        if start == '' or end == '':
            return
        result = invester.backtest(start, end, show_only_text=True, show_plot=True)
        self.bt_result_texts.append(result)
        self.bt_result_list.addItem(f"{symbols} | {start} ~ {end}")
        QMessageBox.information(self, "Done", "Backtesting Done")

    def invest(self):
        
        preset = self._get_preset()
        if preset == {}:
            return
        interval = '30m'
        process_name = f"{preset['title']}_{interval}"
        if process_name in self.processes:
            QMessageBox.warning(self, "Warning", "Process already scheduled for these symbols.")
            return
        symbols = preset['symbols']
        client = kis.KISClient(symbols, preset['max_operate_amount'], nolog=False)
        invester, invester_name = self._get_invester(symbols, client, nobacktest=True, only_backtest=False, only=preset['strategy'])
        
        if invester == None:
            return

        self.process_list_widget.addItem(process_name)
        worker_thread = InvestThread.InvestThread(interval, process_name, invester, self.invest_logs, preset, invester_name)
        if invester_name == "Neo":
            worker_thread.news_reader = self.news_reader
        worker_thread.update_signal.connect(self.update_invest_log_list)
        worker_thread.start()
        self.processes[process_name] = worker_thread
    
    def recommend_stocks(self):
        def chf(pairs, fname):
            processes = []
            result_batch = []
            manager = mp.Manager()
            results = manager.dict()
            start, end = utils.today_and_month_ago()
            for pair in pairs:
                p = mp.Process(target=corr_high_finder.run_backtest, args=(pair, start, end, results))
                processes.append(p)
                p.start()
            for p in processes:
                p.join()
            corr_high_finder.save_results(results, fname=fname)
        processes = []
        result_batch = []
        QMessageBox.information(self, "Warn", "This process needs 30m~1h.")
        for theme_name, theme in utils.THEMES.items():
            start, end = utils.today_and_month_ago()
            pairs = corr_high_finder.filter_pairs(corr_high_finder.get_high_corr_pairs(start, end, theme))
            if len(pairs) == 0:
                continue
            chf(pairs, theme_name)
            
        QMessageBox.information(self, "Done", "Recommendation finishied")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    trading_app = TradingApp()
    trading_app.show()
    sys.exit(app.exec_())