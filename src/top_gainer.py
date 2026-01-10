import datetime
import os
import threading
import time
import pandas as pd
import pytz
import traceback

from ib.ib_top_gainer_data import TopGainerData
from ib.screener_filter import small_cap_pop_filter
from database.sqlite_connector import execute_in_transaction
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException
from exception.cancel_subscription_exception import CancelSubscriptionException

from utils.datetime_util import get_us_business_day

#from utils.logger import Logger

#logger = Logger(filename='nasdaq')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='top gainer scanner connection success', tts=True)
    
    small_cap_pop_search_filter = small_cap_pop_filter()
    small_cap_pop_afterhour_search_filter = small_cap_pop_filter()
    small_cap_pop_afterhour_search_filter.scanCode = 'TOP_AFTER_HOURS_PERC_GAIN'
    
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

        try:
            top_gainer_screener.screener_finished.clear()
            top_gainer_data.data_finished.clear()
            
            if us_current_datetime.time() > datetime.time(16, 0, 0):
                filter = small_cap_pop_afterhour_search_filter
                print('Search by afterhour top gainer filter')
            else:
                filter = small_cap_pop_search_filter
                print('Search by top gainer filter')
            
            top_gainer_screener.reqScannerSubscription(1, filter, [], [])
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
            
            if (datetime.time(16, 0, 0) < us_current_datetime.time().replace(second=0, microsecond=0) <= datetime.time(23, 59, 0)):
                today_top_gainer_count_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                                          WHERE DATE(HIT_SCANNER_DATETIME) = ?
                                                                          AND SCAN_PATTERN = ? 
                                                                          AND BAR_SIZE = ? 
                                                                        """,
                                                                        (us_current_datetime.strftime('%Y-%m-%d'), 'YESTERDAY_BULLISH_DAILY_CANDLE', '1day'))
                today_top_gainer_count = dict(today_top_gainer_count_result[0])['ct']
                
                if today_top_gainer_count > 0:
                    continue
                
                #Deprecated
                #scrap_previous_day_top_gainer()
                afterhour_top_gainer_screener = TopGainerData()
                print(f'Create TWS connection for top gainer screener, clientID: 12')
                afterhour_top_gainer_screener.connect('127.0.0.1', 8888, 12)
                afterhour_screener_api_thread = threading.Thread(target=afterhour_top_gainer_screener.run)
                afterhour_screener_api_thread.name = 'Screener'
                afterhour_screener_api_thread.start()
                # Wait for connection to establish (optional, but good practice)
                time.sleep(5)
                
                afterhour_top_gainer_data = TopGainerData()
                afterhour_top_gainer_data.analyse_previous_day_top_gainer = True
                print(f'Create TWS connection for top gainer data, clientID: 13')
                afterhour_top_gainer_data.connect('127.0.0.1', 8888, 13)
                afterhour_data_api_thread = threading.Thread(target=afterhour_top_gainer_data.run)
                afterhour_data_api_thread.name = 'Data'
                afterhour_data_api_thread.start()
                # Wait for connection to establish (optional, but good practice)
                time.sleep(5) 
    
                afterhour_top_gainer_screener.screener_finished.clear()
                afterhour_top_gainer_screener.reqScannerSubscription(2, small_cap_pop_search_filter, [], [])
                afterhour_top_gainer_screener.screener_finished.wait()
                print('Top gainer screener completed scanning')

                if len(afterhour_top_gainer_screener.error_list) > 0:
                    connection_error = False
                    fatal_error = False
                    error_msg = ''

                    for error in afterhour_top_gainer_screener.error_list:
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
                        afterhour_top_gainer_screener.initialise()
                        raise ConnectionException(error_msg)

                    if fatal_error:
                        afterhour_top_gainer_screener.initialise()
                        raise Exception(error_msg)
                    
                premarket_start_time = us_current_datetime.replace(hour=4, minute=0, second=0)
                timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
                print(f'calculate time interval, start datetime: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end datetime: {us_current_datetime.strftime('%Y-%m-%d %H:%M:%S')}, time difference: {timeframe_interval}')

                if timeframe_interval < 1:
                    print('Timeframe interval less than 1 minute')
                    return

                print(f'fetch {timeframe_interval} min candel for small cap pop scanner, start time: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end time: {us_current_datetime}')

                afterhour_top_gainer_data.small_cap_pop_contract_list = afterhour_top_gainer_screener.small_cap_pop_contract_list
                afterhour_top_gainer_screener.initialise()

                if afterhour_top_gainer_data.small_cap_pop_contract_list:
                    for rank, contract in enumerate(afterhour_top_gainer_data.small_cap_pop_contract_list):
                        afterhour_top_gainer_data.reqHistoricalData((100 + rank), contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
                        afterhour_top_gainer_data.reqHistoricalData((200 + rank), contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
                    afterhour_top_gainer_data.data_finished.wait()

                    if len(afterhour_top_gainer_data.error_list) > 0:
                        connection_error = False
                        fatal_error = False
                        error_msg = ''

                        for error in afterhour_top_gainer_data.error_list:
                            if isinstance(error, ConnectionException):
                                connection_error = True
                                error_msg = str(error)
                                break
                            else:
                                fatal_error = True
                                error_msg = str(error)
                                break
                            
                        if connection_error:
                            afterhour_top_gainer_data.initialise()
                            raise ConnectionException(error_msg)

                        if fatal_error:
                            afterhour_top_gainer_data.initialise()
                            raise Exception(error_msg)
                else:
                    print('No previous day top gainer contract list found')
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