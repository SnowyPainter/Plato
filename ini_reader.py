import configparser

def strategy_settings_MASP(fname):
    config = configparser.ConfigParser()
    config.read(fname, encoding='utf-8')
    return {
        "AMOUNT" : config["ACCOUNT"].getint("AMOUNT"),
        "START_DATE" : config["STRATEGY"]["START"],
        "END_DATE" : config["STRATEGY"]["END"],
        "INTERVAL" : config["STRATEGY"]["INTERVAL"],
        "MABT_W" : config["STRATEGY"].getfloat("MABT_W"),
        "SP_W" : config["STRATEGY"].getfloat("SP_W"),
        "BASIS" : config["STRATEGY"].getfloat("BASIS")
    }