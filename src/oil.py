import os
import threading
import time
import pandas as pd
import traceback

from ibapi.contract import Contract

from ib.cl_index_data import OilIndexData
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

#from utils.logger import Logger

#logger = Logger(filename='Oil')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='Oil scanner connection success', tts=True)
    
    cl_data = OilIndexData()
    print(f'Create TWS connection, clientID: 3')
    cl_data.connect('127.0.0.1', 8888, 7)
    api_thread = threading.Thread(target=cl_data.run)
    api_thread.name = 'CL'
    api_thread.start()
    # Wait for connection to establish (optional, but good practice)
    time.sleep(5) 
    
    while True:
        try:
            cl_data.data_finished.clear()

            cl_contract = Contract()
            cl_contract.symbol = "CL"
            cl_contract.secType = "CONTFUT"
            cl_contract.exchange = "NYMEX"
            
            # 1day = 1440 minutes = 86400 seconds
            timeframe_interval = 1440

            cl_data.reqHistoricalData(70000, cl_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            cl_data.reqHistoricalData(71000, cl_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            cl_data.data_finished.wait()
            
            if len(cl_data.error_list) > 0:
                connection_error = False
                fatal_error = False
                error_msg = ''
                
                for error in cl_data.error_list:
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
            time.sleep(3)
        except Exception as e:
            cl_data.error_list = []
            
            if isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing Oil scanner connection due to connectivity issue')
                #logger.log_debug_msg('Re-establishing Oil scanner connection due to connectivity issue')
                send_message(channel=MAIN_BOT, message='Re-establishing Oil scanner connection due to connectivity issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                print('Re-establishing Oil scanner connection due to fatal error')
                #logger.log_debug_msg(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Oil scanner connection due to fatal error', tts=True)
            if sleep_time:
                time.sleep(sleep_time)
                sleep_time = None
                continue
        
        print('Completed Oil index analysis')
if __name__ == '__main__':
    main()