import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
    QLineEdit, QCheckBox, QDialog, QMessageBox, QListWidget, QInputDialog
)

# Preset Dialog
class SavePresetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Preset")

        self.layout = QVBoxLayout()

        self.title_label = QLabel("Title:")
        self.title_input = QLineEdit()
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.title_input)

        self.symbol1_label = QLabel("Symbol 1:")
        self.symbol1_input = QLineEdit()
        self.layout.addWidget(self.symbol1_label)
        self.layout.addWidget(self.symbol1_input)

        self.symbol2_label = QLabel("Symbol 2:")
        self.symbol2_input = QLineEdit()
        self.layout.addWidget(self.symbol2_label)
        self.layout.addWidget(self.symbol2_input)

        self.max_operate_label = QLabel("Max Operate Amount:")
        self.max_operate_input = QLineEdit()
        self.layout.addWidget(self.max_operate_label)
        self.layout.addWidget(self.max_operate_input)

        self.stoploss_label = QLabel("Stoploss:")
        self.stoploss_input = QLineEdit()
        self.layout.addWidget(self.stoploss_label)
        self.layout.addWidget(self.stoploss_input)

        self.takeprofit_label = QLabel("Takeprofit:")
        self.takeprofit_input = QLineEdit()
        self.layout.addWidget(self.takeprofit_label)
        self.layout.addWidget(self.takeprofit_input)

        self.stoploss_check = QCheckBox("Enable Stoploss")
        self.layout.addWidget(self.stoploss_check)

        self.takeprofit_check = QCheckBox("Enable Takeprofit")
        self.layout.addWidget(self.takeprofit_check)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_preset)
        self.layout.addWidget(self.save_button)

        self.setLayout(self.layout)

    def save_preset(self):
        preset = {
            "title": self.title_input.text(),
            "symbol1": self.symbol1_input.text(),
            "symbol2": self.symbol2_input.text(),
            "max_operate_amount": float(self.max_operate_input.text()),
            "stoploss": float(self.stoploss_input.text()),
            "takeprofit": float(self.takeprofit_input.text()),
            "enable_stoploss": self.stoploss_check.isChecked(),
            "enable_takeprofit": self.takeprofit_check.isChecked()
        }
        if not os.path.exists('./presets'):
            os.makedirs('./presets')
        if os.path.exists(f"./presets/{preset['title']}.json"):
            QMessageBox.information(self, "Error", "Use other name of preset.")
            return
        with open(f"./presets/{preset['title']}.json", 'w') as f:
            json.dump(preset, f, indent=4)

        QMessageBox.information(self, "Saved", "Preset saved successfully!")
        self.close()
        
def get_presets():
    if not os.path.exists('./presets'):
        QMessageBox.warning(self, "Error", "No presets found!")
        return []

    presets = os.listdir('./presets')
    if not presets:
        QMessageBox.warning(self, "Error", "No presets found!")
        return []

    preset_titles = [preset.replace('.json', '') for preset in presets]
    return preset_titles
                
def get_preset_details(preset):
    details = (
        f"Title: {preset['title']}\n"
        f"Symbol 1: {preset['symbol1']}\n"
        f"Symbol 2: {preset['symbol2']}\n"
        f"Max Operate Amount: {preset['max_operate_amount']}\n"
        f"Stoploss: {preset['stoploss']} (Enabled: {preset['enable_stoploss']})\n"
        f"Takeprofit: {preset['takeprofit']} (Enabled: {preset['enable_takeprofit']})"
    )
    return details

def update_preset(preset, key, value):
    if not os.path.exists(f"./presets/{preset['title']}.json"):
        return
    preset[key] = value
    with open(f"./presets/{preset['title']}.json", 'w') as f:
        json.dump(preset, f, indent=4)
    