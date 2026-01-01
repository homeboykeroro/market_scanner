import datetime
import os
import threading
import time
import pandas as pd
import pytz
import traceback

from ibapi.contract import Contract

from ib.ym_index_data import DowJonesIndexData
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

#from utils.logger import Logger

#logger = Logger(filename='Dow Jones')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='Dow Jones scanner connection success', tts=True)
    
    ym_data = DowJonesIndexData()
    print(f'Create TWS connection, clientID: 3')
    ym_data.connect('127.0.0.1', 8888, 3)
    api_thread = threading.Thread(target=ym_data.run)
    api_thread.name = 'YM'
    api_thread.start()
    # Wait for connection to establish (optional, but good practice)
    time.sleep(5) 
    
    while True:
        try:
            ym_data.data_finished.clear()

            ym_contract = Contract()
            ym_contract.symbol = "YM"
            ym_contract.secType = "CONTFUT"
            ym_contract.exchange = "CBOT"
            
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            premarket_start_time = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return

            ym_data.reqHistoricalData(30000, ym_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            ym_data.reqHistoricalData(31000, ym_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            ym_data.data_finished.wait()
            time.sleep(5)
        except Exception as e:
            if isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing Dow Jones scanner connection due to connectivity issue')
                #logger.log_debug_msg('Re-establishing Dow Jones scanner connection due to connectivity issue')
                ym_data.data_finished.clear()
                send_message(channel=MAIN_BOT, message='Re-establishing Dow Jones scanner connection due to connectivity issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                print('Re-establishing Dow Jones scanner connection due to fatal error')
                #logger.log_debug_msg(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Dow Jones scanner connection due to fatal error', tts=True)
            if sleep_time:
                time.sleep(sleep_time)
                sleep_time = None
                continue
        
        print('Completed Dow Jones index analysis')
if __name__ == '__main__':
    main()