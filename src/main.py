import datetime
import time
import pandas as pd
import pytz
import os
import traceback

from ibapi.contract import Contract

from ib.ib_client import IBClient
from ib.screener_filter import small_cap_pop_filter
from discord.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

from pattern.small_cap_pop import analyse_small_cap_pop
from pattern.small_cap_ramp_up import analyse_small_cap_ramp_up
from pattern.yesterday_bullish_daily_candle import analyse_yesterday_bullish_daily_candle
from pattern.indice_pop import analyse_index_pop

idx = pd.IndexSlice

def main():
    ib_client = IBClient()
    
    send_message(channel=MAIN_BOT, message='TWS connection success', tts=True)
    
    while True:  
        #Initialise data
        ib_client.small_cap_pop_contract_list = []
        ib_client.small_cap_pop_df_dict = {}
        ib_client.small_cap_pop_previous_day_df_dict = {}
        ib_client.small_cap_pop_minute_df = None
        ib_client.small_cap_pop_daily_df = None
        ib_client.nq_minute_df = None
        ib_client.nq_daily_df = None
        ib_client.es_minute_df = None
        ib_client.es_daily_df = None
        ib_client.ym_minute_df = None
        ib_client.ym_daily_df = None
        ib_client.nq_futures_df_dict = {}
        ib_client.es_futures_df_dict = {}
        ib_client.ym_futures_df_dict = {}
        ib_client.nq_futures_previous_day_df_dict = {}
        ib_client.es_futures_previous_day_df_dict = {}
        ib_client.ym_futures_previous_day_df_dict = {}
        
        #Top gainer screener
        scan_time = time.time()
        try:
            print('Scanning top gainer')
            ib_client.connect('127.0.0.1', 8888, 0)
            
            small_cap_pop_search_filter = small_cap_pop_filter()
            ib_client.reqScannerSubscription(2, small_cap_pop_search_filter, [], [])
            ib_client.run()
        except Exception as e:
            if isinstance(e, TypeError) and str(e) == "'>=' not supported between instances of 'NoneType' and 'int'":
                sleep_time = None
                print('refreshed top gainer scanner...')
            elif isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Connectivity Issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Fatal Error', tts=True)

            if sleep_time:
                time.sleep(sleep_time)
                continue
        print(f'top gainer scan time: {time.time() - scan_time} seconds')
        
        #fetch candle data
        top_gainer_candle_data_start_time = time.time()
        try:
            ib_client.connect('127.0.0.1', 8888, 0)
            print(f'top gainer scanner ticker list: {[contract.symbol for contract in ib_client.small_cap_pop_contract_list]}')
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            premarket_start_time = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return
            
            print(f'fetch {timeframe_interval} min candel for small cap pop scanner, start time: {premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')}, end time: {us_current_datetime}')
            for rank, contract in enumerate(ib_client.small_cap_pop_contract_list):
                ib_client.reqHistoricalData((100 + rank), contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
                ib_client.reqHistoricalData((200 + rank), contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            
            nq_contract = Contract()
            nq_contract.symbol = "NQ"
            nq_contract.secType = "CONTFUT"
            nq_contract.exchange = "CME"
            
            es_contract = Contract()
            es_contract.symbol = "ES"
            es_contract.secType = "CONTFUT"
            es_contract.exchange = "CME"
            
            ym_contract = Contract()
            ym_contract.symbol = "YM"
            ym_contract.secType = "CONTFUT"
            ym_contract.exchange = "CBOT"
    
            ib_client.reqHistoricalData(10000, nq_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            ib_client.reqHistoricalData(11000, nq_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            ib_client.reqHistoricalData(20000, es_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            ib_client.reqHistoricalData(21000, es_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            ib_client.reqHistoricalData(30000, ym_contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
            ib_client.reqHistoricalData(31000, ym_contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])
            
            ib_client.run()
        except Exception as e:
            if isinstance(e, TypeError) and str(e) == "'>=' not supported between instances of 'NoneType' and 'int'":
                sleep_time = None
                print('candle data retrieval completed...')
            elif isinstance(e, ConnectionException):
                sleep_time = 180

                os.system('cls')
                print(f'TWS API Connection Lost, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Connectivity Issue', tts=True)
            else:
                sleep_time = 10

                os.system('cls')
                print(traceback.format_exc())
                print(f'Fatal Error, Cause: {e}')
                send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Fatal Error', tts=True)

            if sleep_time:
                time.sleep(sleep_time)
                continue    
        print(f'candle data retrieval time: {time.time() - top_gainer_candle_data_start_time} seconds')

        try:
            if len(ib_client.small_cap_pop_contract_list):
                analyse_small_cap_pop(ib_client.small_cap_pop_minute_df, ib_client.small_cap_pop_daily_df)
                analyse_small_cap_ramp_up(ib_client.small_cap_pop_minute_df, ib_client.small_cap_pop_daily_df)
                #analyse_yesterday_bullish_daily_candle(ib_client.small_cap_pop_minute_df, ib_client.small_cap_pop_daily_df)
            
            analyse_index_pop(ib_client.nq_minute_df, ib_client.nq_daily_df, 'NQ')
            analyse_index_pop(ib_client.es_minute_df, ib_client.es_daily_df, 'ES')
            analyse_index_pop(ib_client.ym_minute_df, ib_client.ym_daily_df, 'YM')
        except Exception as e:
            os.system('cls')
            print(traceback.format_exc())
            print(f'Fatal Error, Cause: {e}')
            send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Fatal Error', tts=True)
            time.sleep(10)
            continue
        
if __name__ == '__main__':
    main()