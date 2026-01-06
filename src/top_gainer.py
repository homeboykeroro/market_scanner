import datetime
import os
import threading
import time
import pandas as pd
import pytz
import traceback

from ib.ib_top_gainer_data import TopGainerData
from ib.screener_filter import small_cap_pop_filter
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException
from exception.cancel_subscription_exception import CancelSubscriptionException

from utils.previous_day_top_gainer_scraper import scrap_previous_day_top_gainer
from utils.datetime_util import get_us_business_day

#from utils.logger import Logger

#logger = Logger(filename='nasdaq')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='top gainer scanner connection success', tts=True)
    
    small_cap_pop_search_filter = small_cap_pop_filter()
    top_gainer_screener = TopGainerData()
    print(f'Create TWS connection for top gainer screener, clientID: 10')
    top_gainer_screener.connect('127.0.0.1', 8888, 10)
    screener_api_thread = threading.Thread(target=top_gainer_screener.run)
    screener_api_thread.name = 'Screener'
    screener_api_thread.start()
    # Wait for connection to establish (optional, but good practice)
    time.sleep(5)
    
    top_gainer_data = TopGainerData()
    print(f'Create TWS connection for top gainer data, clientID: 11')
    top_gainer_data.connect('127.0.0.1', 8888, 11)
    data_api_thread = threading.Thread(target=top_gainer_data.run)
    data_api_thread.name = 'Data'
    data_api_thread.start()
    # Wait for connection to establish (optional, but good practice)
    time.sleep(5) 
    
    while True:
        us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
        
        if us_current_datetime.date() != get_us_business_day(0, us_current_datetime).date():
            print('Top gainer scanner is idle... (Holiday)')
            continue
        
        if not (datetime.time(4, 0, 0) < us_current_datetime.time() < datetime.time(20, 0, 0)):
            print('Top gainer scanner is idle... (Outside regular trading hours)')
            continue
        
        if (datetime.time(16, 0, 0) < us_current_datetime.time().replace(second=0, microsecond=0) <= datetime.time(23, 59, 0)):
            scrap_previous_day_top_gainer()

        try:
            top_gainer_screener.screener_finished.clear()
            top_gainer_data.data_finished.clear()
            
            top_gainer_screener.reqScannerSubscription(1, small_cap_pop_search_filter, [], [])
            top_gainer_screener.screener_finished.wait()
            print('Top gainer screener completed scanning')
            
            if len(top_gainer_screener.error_list) > 0:
                connection_error = False
                fatal_error = False
                error_msg = ''
                
                for error in top_gainer_screener.error_list:
                    if isinstance(error, ConnectionException):
                        connection_error = True
                        error_msg = str(error)
                        break
                    elif isinstance(error, CancelSubscriptionException):
                        connection_error = False
                        fatal_error = False
                    else:
                        fatal_error = True
                        error_msg = str(error)
                        break
                
                if connection_error:
                    top_gainer_screener.initialise()
                    raise ConnectionException(error_msg)
                
                if fatal_error:
                    top_gainer_screener.initialise()
                    raise Exception(error_msg)
            
            premarket_start_time = us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            print(f'calculate time interval, start datetime: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end datetime: {us_current_datetime.strftime('%Y-%m-%d %H:%M:%S')}, time difference: {timeframe_interval}')
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return

            print(f'fetch {timeframe_interval} min candel for small cap pop scanner, start time: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end time: {us_current_datetime}')
            
            top_gainer_data.small_cap_pop_contract_list = top_gainer_screener.small_cap_pop_contract_list
            top_gainer_screener.initialise()
            
            if top_gainer_data.small_cap_pop_contract_list:
                for rank, contract in enumerate(top_gainer_data.small_cap_pop_contract_list):
                    top_gainer_data.reqHistoricalData((100 + rank), contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
                    top_gainer_data.reqHistoricalData((200 + rank), contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
                top_gainer_data.data_finished.wait()
                
                if len(top_gainer_data.error_list) > 0:
                    connection_error = False
                    fatal_error = False
                    error_msg = ''

                    for error in top_gainer_data.error_list:
                        if isinstance(error, ConnectionException):
                            connection_error = True
                            error_msg = str(error)
                            break
                        else:
                            fatal_error = True
                            error_msg = str(error)
                            break
                        
                    if connection_error:
                        top_gainer_data.initialise()
                        raise ConnectionException(error_msg)

                    if fatal_error:
                        top_gainer_data.initialise()
                        raise Exception(error_msg)
            else:
                print('No top gainer contract list found')
            
            time.sleep(5)
        except Exception as e:
            if isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing top gainer scanner connection due to connectivity issue')
                #logger.log_debug_msg('Re-establishing top gainer scanner connection due to connectivity issue')
                send_message(channel=MAIN_BOT, message='Re-establishing top gainer scanner connection due to connectivity issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                print('Re-establishing top gainer scanner connection due to fatal error')
                #logger.log_debug_msg(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing top gainer scanner connection due to fatal error', tts=True)
            if sleep_time:
                time.sleep(sleep_time)
                sleep_time = None
                continue
        
        print('Completed top gainer index analysis')
if __name__ == '__main__':
    main()