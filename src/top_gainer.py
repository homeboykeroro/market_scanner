import datetime
import random
import threading
import time
import pandas as pd
import pytz
import traceback

from ibapi.contract import Contract

from ib.ib_top_gainer_data import TopGainerData
from ib.screener_filter import small_cap_pop_filter
from notification.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

#from utils.logger import Logger

#logger = Logger(filename='nasdaq')
idx = pd.IndexSlice

def main():
    send_message(channel=MAIN_BOT, message='top gainer scanner connection success', tts=True)
    current_top_gainer_screener_client_id = None
    top_gainer_screener = None
    current_top_gainer_data_client_id = None
    top_gainer_data = None
    
    while True:
        try:
            top_gainer_screener = TopGainerData()
            current_top_gainer_screener_client_id = random.randint(1, 100)
            print(f'Create TWS connection for top gainer screener, clientID: {current_top_gainer_screener_client_id}')
            top_gainer_screener.connect('127.0.0.1', 8888, current_top_gainer_screener_client_id)
            api_thread = threading.Thread(target=top_gainer_screener.run, daemon=True)
            api_thread.start()

            # Wait for connection to establish (optional, but good practice)
            time.sleep(1) 
            
            small_cap_pop_search_filter = small_cap_pop_filter()
            top_gainer_screener.reqScannerSubscription(1, small_cap_pop_search_filter, [], [])
            top_gainer_screener.screener_finished.wait()
            print(f'Close TWS connection for top gainer screener, clientID: {top_gainer_data.clientId}')
            top_gainer_screener.disconnect()
            print('Top gainer screener completed scanning')
            
            top_gainer_data = TopGainerData()
            current_top_gainer_data_client_id = random.randint(200, 300)
            print(f'Create TWS connection for top gainer data, clientID: {current_top_gainer_data_client_id}')
            top_gainer_data.connect('127.0.0.1', 8888, current_top_gainer_data_client_id)
            api_thread = threading.Thread(target=top_gainer_data.run, daemon=True)
            api_thread.start()

            # Wait for connection to establish (optional, but good practice)
            time.sleep(1) 
            
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            premarket_start_time = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return

            print(f'fetch {timeframe_interval} min candel for small cap pop scanner, start time: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end time: {us_current_datetime}')
            for rank, contract in enumerate(top_gainer_data.small_cap_pop_contract_list):
                top_gainer_data.reqHistoricalData((100 + rank), contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
                top_gainer_data.reqHistoricalData((200 + rank), contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            top_gainer_data.data_finished.wait()
            print(f'Close TWS connection for top gainer data, clientID: {top_gainer_data.clientId}')
            top_gainer_data.disconnect()
        except Exception as e:
            if isinstance(e, ConnectionException):
                sleep_time = 180

                #os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                print('Re-establishing top gainer scanner connection due to connectivity issue')
                #logger.log_debug_msg('Re-establishing top gainer scanner connection due to connectivity issue')
                send_message(channel=MAIN_BOT, message='Re-establishing top gainer scanner connection due to connectivity issue', tts=True)
            else:
                sleep_time = 10

                #os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                #logger.log_debug_msg(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing top gainer scanner connection due to fatal error', tts=True)
            if sleep_time:
                time.sleep(sleep_time)
                sleep_time = None
                continue
        
        print('Completed top gainer index analysis')
if __name__ == '__main__':
    main()