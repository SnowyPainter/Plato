class MABreakThrough:
    def action(self, symbols, data):
        buy_list = []
        sell_list = []
        for symbol in symbols:
            column = symbol + "_Price"
            if data["LMA"][column] > data["SMA"][column]:
                sell_list.append(symbol)
            elif data["SMA"][column] > data["LMA"][column]:
                buy_list.append(symbol)
        return buy_list, sell_list
            