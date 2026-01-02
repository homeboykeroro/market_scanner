import datetime
import os
import threading
import time
import pandas as pd
import pytz
import traceback

from ibapi.contract import Contract

from ib.es_index_data import SP500IndexData
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

from utils.datetime_util import get_us_business_day

#from utils.logger import Logger

#logger = Logger('sp500')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='S&P500 scanner connection success', tts=True)
    
    es_data = SP500IndexData()
    print(f'Create TWS connection, clientID: 2')
    es_data.connect('127.0.0.1', 8888, 2)
    api_thread = threading.Thread(target=es_data.run)
    api_thread.name = 'ES'
    api_thread.start()
    # Wait for connection to establish (optional, but good practice)
    time.sleep(5) 
    
    while True:
        try:
            es_data.data_finished.clear()
    
            es_contract = Contract()
            es_contract.symbol = "ES"
            es_contract.secType = "CONTFUT"
            es_contract.exchange = "CME"
            
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            previous_us_business_day = get_us_business_day(-1, us_current_datetime)
            nearest_trading_day = get_us_business_day(0, us_current_datetime)
            previous_day_premarket_start_time = previous_us_business_day.replace(hour=4, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
            print(f'previous us business day: {previous_day_premarket_start_time},  nearest trading day: {nearest_trading_day}')
            timeframe_interval = int(((nearest_trading_day - previous_day_premarket_start_time).total_seconds()) / 60)
            print(f'calculate time interval, start datetime: {previous_day_premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end datetime: {nearest_trading_day.strftime('%Y-%m-%d %H:%M:%S')}, time difference: {timeframe_interval}')
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return

            es_data.reqHistoricalData(20000, es_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            es_data.reqHistoricalData(21000, es_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            es_data.data_finished.wait()
            time.sleep(5)
        except Exception as e:
            if isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing S&P500 scanner connection due to connectivity issue')
                #logger.log_debug_msg('Re-establishing S&P500 scanner connection due to connectivity issue')
                send_message(channel=MAIN_BOT, message='Re-establishing S&P500 scanner connection due to connectivity issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                print('Re-establishing S&P500 scanner connection due to fatal error')
                #logger.log_debug_msg(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing S&P500 scanner connection due to fatal error', tts=True)
            if sleep_time:
                time.sleep(sleep_time)
                sleep_time = None
                continue
        
        print('Completed S&P500 index analysis')
if __name__ == '__main__':
    main()