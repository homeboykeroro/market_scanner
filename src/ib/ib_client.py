
import datetime
import re
from ibapi.client import *
from ibapi.wrapper import *
import pandas as pd
import pytz

from discord.discord_client import send_message, MAIN_BOT
from exception.connection_exception import ConnectionException
from utils.dataframe_util import append_customised_indicator

from utils.logger import Logger

logger = Logger()

class IBClient(EClient, EWrapper):
    small_cap_pop_contract_list = []
    small_cap_pop_df_dict = {}
    small_cap_pop_previous_day_df_dict = {}
    
    def __init__(self):
        EClient.__init__(self, self)
     
    def connectAck(self):
        send_message(channel=MAIN_BOT, message='TWS connection success', tts=True)
        
    def error(self,
        reqId: TickerId,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson=""):
        ''' Callbacks to EWrapper with errorId as -1 do not represent true 'errors' but only 
        notification that a connector has been made successfully to the IB market data farms. '''
        success_error_code_list = [2104, 2105, 2106, 2108, 2158]
        ''' Error code 165 is used to by pass error of Historical Market Data Service query message:no items retrieved '''
        bypass_fatal_error_code_list = [165]
        connection_error_code_list = [1100, 1101, 1102, 2110, 2103]

        if errorCode in success_error_code_list:
            connect_success_msg = f'reqId: {reqId}, TWS Connection Success, errorCode: {errorCode}, message: {errorString}'
        elif errorCode in bypass_fatal_error_code_list:
            bypass_error_msg = f'reqId: {reqId}, By pass TWS error, errorCode: {errorCode}, message: {errorString}'
        elif errorCode in connection_error_code_list:
            connect_fail_msg = f'reqId: {reqId}, TWS Connection Error, errorCode: {errorCode}, message: {errorString}'
            raise ConnectionException(connect_fail_msg)
        else:
            fatal_error_msg = f'reqId: {reqId}, TWS Fatal Error, errorCode: {errorCode}, message: {errorString}'
            raise Exception(fatal_error_msg)

    def scannerData(self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr):
        # print(f"scannerData. reqId: {reqId}, rank: {rank}, contractDetails: {contractDetails}, distance: {distance}, benchmark: {benchmark}, projection: {projection}, legsStr: {legsStr}.")

        # Small cap pop scan
        if reqId == 1:
            if rank == 0:
                self.small_cap_pop_contract_list = []
            
            if re.match('^[a-zA-Z]{1,4}$', contractDetails.contract.symbol): 
                self.small_cap_pop_contract_list.append(contractDetails.contract)

    def historicalData(self, reqId: int, bar: BarData):
        open = bar.open
        high = bar.high
        low = bar.low
        close = bar.close
        volume = bar.volume
        dt = bar.date.replace(" US/Eastern", "")
        
        if 100 <= reqId < 200:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            ticker = self.small_cap_pop_contract_list[reqId - 100].symbol
            
            if ticker not in self.small_cap_pop_df_dict:
                self.small_cap_pop_df_dict[ticker] = {}
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([[ticker], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.small_cap_pop_df_dict[ticker][formated_dt] = single_ticker_candle_df
            # print(f'fetch {ticker} {formated_dt}')
            
        if 200 <= reqId < 300:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d').strftime('%Y-%m-%d')
            ticker = self.small_cap_pop_contract_list[reqId - 200].symbol
            
            if ticker not in self.small_cap_pop_previous_day_df_dict:
                self.small_cap_pop_previous_day_df_dict[ticker] = {}
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([[ticker], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.small_cap_pop_previous_day_df_dict[ticker][formated_dt] = single_ticker_candle_df
            
    #Marks the ending of historical bars reception.
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        if (len(self.small_cap_pop_df_dict) == len(self.small_cap_pop_contract_list)
                and len(self.small_cap_pop_previous_day_df_dict) == len(self.small_cap_pop_contract_list)):
            ticker_minute_df_list = []
            ticker_daily_df_list= []
            
            for ticker, minute_df_dict in self.small_cap_pop_df_dict.items():
                minute_df_list = []
                
                for dt, minute_df in minute_df_dict.items():
                    minute_df_list.append(minute_df)
                    
                single_ticker_minute_df = pd.concat(minute_df_list, axis=0)
                ticker_minute_df_list.append(single_ticker_minute_df)
            
            complete_minute_df = pd.concat(ticker_minute_df_list, axis=1)
            
            with pd.option_context('display.max_rows', None,
                                       'display.max_columns', None,
                                    'display.precision', 3):
                logger.log_debug_msg(complete_minute_df)
            
            complete_minute_df = append_customised_indicator(complete_minute_df)
            
            for ticker, daily_df_dict in self.small_cap_pop_previous_day_df_dict.items():
                daily_df_list = []
                
                for dt, daily_df in daily_df_dict.items():
                    daily_df_list.append(daily_df)
                    
                single_ticker_candle_df = pd.concat(daily_df_list, axis=0)
                ticker_daily_df_list.append(single_ticker_candle_df)
            
            complete_daily_df = pd.concat(ticker_daily_df_list, axis=1)
            
            with pd.option_context('display.max_rows', None,
                                       'display.max_columns', None,
                                    'display.precision', 3):
                logger.log_debug_msg(complete_daily_df)
            
            complete_daily_df = append_customised_indicator(complete_daily_df)
            
            print()
    
    def scannerDataEnd(self, reqId):
        # Small cap pop scan
        if reqId == 1:
            print(f'top gainer scanner ticker list: {[contract.symbol for contract in self.small_cap_pop_contract_list]}')
            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            premarket_start_time = us_current_datetime.replace(hour=4, minute=0, second=0)
            timeframe_interval = int(((us_current_datetime - premarket_start_time).total_seconds()) / 60)
            
            if timeframe_interval < 1:
                print('Timeframe interval less than 1 minute')
                return
            
            print(f'fetch {timeframe_interval} min candel for small cap pop scanner, start time: 04:00:00, end time: {us_current_datetime}')
            
            for rank, contract in enumerate(self.small_cap_pop_contract_list):
                self.reqHistoricalData((100 + rank), contract, '', f'{str(int(timeframe_interval * 60))} S', '1 min', 'TRADES', 0, 1, False, [])
                self.reqHistoricalData((200 + rank), contract, '', '2 D', '1 day', 'TRADES', 1, 1, False, [])

