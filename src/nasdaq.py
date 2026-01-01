import datetime
import os
import threading
import time
import pandas as pd
import pytz
import traceback
import queue

from ibapi.contract import Contract

from ib.nq_index_data import NasdaqIndexData
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

from utils.datetime_util import get_us_business_day

#from utils.logger import Logger

#logger = Logger(filename='nasdaq')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='Nasdaq scanner connection success', tts=True)
    
    nq_data = NasdaqIndexData()
    
    def thread_target_with_exception_handling(target_func, result_queue):
        """Wrapper that runs the target and puts any exception into the queue"""
        try:
            target_func()
        except Exception as e:
            # Capture full traceback
            tb = traceback.format_exc()
            result_queue.put(('error', e, tb))
        else:
            result_queue.put(('success', None, None))

    # Usage
    result_queue = queue.Queue()
    
    print(f'Create TWS connection, clientID: 1')
    nq_data.connect('127.0.0.1', 8888, 1)
    wrapped_target = lambda: thread_target_with_exception_handling(nq_data.run, result_queue)
    api_thread = threading.Thread(target=wrapped_target)
    api_thread.name = 'NQ'    
    api_thread.start()
    # Wait for connection to establish (optional, but good practice)
    time.sleep(5) 
    
    while True:
        try:
            nq_data.data_finished.clear()
            
            nq_contract = Contract()
            nq_contract.symbol = "NQ"
            nq_contract.secType = "CONTFUT"
            nq_contract.exchange = "CME"
            
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            previous_us_business_day = get_us_business_day(-1, us_current_datetime)
            print(f'previous US business day: {previous_us_business_day.strftime('%Y-%m-%d %H:%M:%S')}')
            premarket_start_time = previous_us_business_day.replace(hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            print(f'calculate time interval, start datetime: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end datetime: {us_current_datetime.strftime('%Y-%m-%d %H:%M:%S')}, time difference: {timeframe_interval}')
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return

            nq_data.reqHistoricalData(10000, nq_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            nq_data.reqHistoricalData(11000, nq_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            nq_data.data_finished.wait()
            time.sleep(5)
        except Exception as e:
            if isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing Nasdaq scanner connection due to connectivity issue')
                #logger.log_debug_msg('Re-establishing Nasdaq scanner connection due to connectivity issue')
                send_message(channel=MAIN_BOT, message='Re-establishing Nasdaq scanner connection due to connectivity issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                print('Re-establishing Nasdaq scanner connection due to fatal error')
                #logger.log_debug_msg(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Nasdaq scanner connection due to fatal error', tts=True)
            if sleep_time:
                time.sleep(sleep_time)
                sleep_time = None
                continue
        
        print('Completed Nasdaq index analysis')
if __name__ == '__main__':
    main()