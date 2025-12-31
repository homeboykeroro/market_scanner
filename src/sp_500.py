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

#from utils.logger import Logger

#logger = Logger('sp500')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='S&P500 scanner connection success', tts=True)
    es_data = None
    
    while True:
        try:
            es_data = SP500IndexData()
            print(f'Create TWS connection, clientID: 2')
            es_data.connect('127.0.0.1', 8888, 2)
            api_thread = threading.Thread(target=es_data.run, daemon=True)
            api_thread.name = 'ES'
            api_thread.start()

            # Wait for connection to establish (optional, but good practice)
            time.sleep(1) 
    
            es_contract = Contract()
            es_contract.symbol = "ES"
            es_contract.secType = "CONTFUT"
            es_contract.exchange = "CME"
            
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            premarket_start_time = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return

            es_data.reqHistoricalData(20000, es_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            es_data.reqHistoricalData(21000, es_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            es_data.data_finished.wait()
            print(f'Close TWS connection, clientID: {es_data.clientId}')
            es_data.disconnect()
        except Exception as e:
            if isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing S&P500 scanner connection due to connectivity issue')
                print('Disconnecting...')
                es_data.disconnect()
                es_data.data_finished.set()
                print('Terminate TWS thread...')
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