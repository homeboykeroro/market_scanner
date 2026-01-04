import os
import threading
import time
import pandas as pd
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
            
            # 1day = 1440 minutes = 86400 seconds
            timeframe_interval = 1440

            es_data.reqHistoricalData(20000, es_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            es_data.reqHistoricalData(21000, es_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            es_data.data_finished.wait()
            
            if len(es_data.error_list) > 0:
                connection_error = False
                fatal_error = False
                error_msg = ''
                
                for error in es_data.error_list:
                    if isinstance(error, ConnectionException):
                        connection_error = True
                        error_msg = str(error)
                        break
                    else:
                        fatal_error = True
                        error_msg = str(error)
                        break
                
                if connection_error:
                    raise ConnectionException(error_msg)
                
                if fatal_error:
                    raise Exception(error_msg)
            time.sleep(5)
        except Exception as e:
            es_data.error_list = []
            
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