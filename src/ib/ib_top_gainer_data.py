import datetime
import threading
import re
import pandas as pd
import pytz

from ibapi.client import *
from ibapi.wrapper import *

from exception.connection_exception import ConnectionException

from utils.dataframe_util import append_customised_indicator
#from utils.logger import Logger

from pattern.small_cap_pop import analyse_small_cap_pop
from pattern.small_cap_ramp_up import analyse_small_cap_ramp_up
from pattern.yesterday_bullish_daily_candle import analyse_yesterday_bullish_daily_candle

#logger = Logger()

class TopGainerData(EClient, EWrapper):
    small_cap_pop_contract_list = []
    small_cap_pop_df_dict = {}
    small_cap_pop_previous_day_df_dict = {}
    
    def __init__(self):
        EClient.__init__(self, self)
        self.initialise()
        self.screener_finished = threading.Event() 
        self.data_finished = threading.Event() 

    def initialise(self):
        self.small_cap_pop_contract_list = []
        self.small_cap_pop_df_dict = {}
        self.small_cap_pop_previous_day_df_dict = {}
     
    # def connectAck(self):
    #     send_message(channel=MAIN_BOT, message='TWS connection success', tts=True)
        
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
            if errorCode == -1 or errorCode == 502:
                connect_fail_msg = f'reqId: {reqId}, TWS Connection Error, errorCode: {errorCode}, message: {errorString}'
                raise ConnectionException(connect_fail_msg)
            
            fatal_error_msg = f'reqId: {reqId}, TWS Fatal Error, errorCode: {errorCode}, message: {errorString}'
            raise Exception(fatal_error_msg)

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
            #print(f'fetch {ticker} {formated_dt}')
            
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
        if 100 <= reqId < 200:
            print(f'clientID: {self.clientId}, {self.small_cap_pop_contract_list[reqId - 100].symbol} minute candle, start: {start}, end: {end}') 
        
        if 200 <= reqId < 300:
            print(f'clientID: {self.clientId}, {self.small_cap_pop_contract_list[reqId - 200].symbol} daily candle, start: {start}, end: {end}') 
            
        us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
        premarket_start_time = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
        premarket_start_time = premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')
            
        if (self.small_cap_pop_df_dict 
                and self.small_cap_pop_contract_list
                and len(self.small_cap_pop_df_dict) == len(self.small_cap_pop_contract_list)
                and len(self.small_cap_pop_previous_day_df_dict) == len(self.small_cap_pop_contract_list)):
            ticker_minute_df_list = []
            ticker_daily_df_list= []
            
            for ticker, minute_df_dict in self.small_cap_pop_df_dict.items():
                minute_df_list = []
                
                for dt, minute_df in minute_df_dict.items():
                    minute_df_list.append(minute_df)
                    
                single_ticker_minute_df = pd.concat(minute_df_list, axis=0)
                
                #ensure the minute candle dataframe start datetime is premarket datetime
                single_ticker_minute_df = single_ticker_minute_df.loc[premarket_start_time:, :]
                print(f'{single_ticker_minute_df.columns.get_level_values(0)[0]} concat minute candle start datetime: {single_ticker_minute_df.iloc[[0]].index[0]}, end datetime: {single_ticker_minute_df.iloc[[-1]].index[0]}')
                
                #reindex to unify all minute candle dataframes have same dimension
                #even though get error in current datetime difference, should be 1 minute at most
                datetime_range_index = pd.date_range(start=premarket_start_time, end=us_current_datetime.strftime('%Y-%m-%d %H:%M:%S'), freq='1min').strftime('%Y-%m-%d %H:%M:%S')
                single_ticker_minute_df = single_ticker_minute_df.reindex(datetime_range_index).ffill()
                print(f'{single_ticker_minute_df.columns.get_level_values(0)[0]} reindexed concat minute candle start datetime: {single_ticker_minute_df.iloc[[0]].index[0]}, end datetime: {single_ticker_minute_df.iloc[[-1]].index[0]}')
                
                ticker_minute_df_list.append(single_ticker_minute_df)
            
            complete_minute_df = pd.concat(ticker_minute_df_list, axis=1)
            complete_minute_df = append_customised_indicator(complete_minute_df)
            
            print(f'{single_ticker_minute_df.columns.get_level_values(0)[0]} complete minute candle start datetime: {single_ticker_minute_df.iloc[[0]].index[0]}, end datetime: {single_ticker_minute_df.iloc[[-1]].index[0]}')
            
            #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_minute_df)
            
            for ticker, daily_df_dict in self.small_cap_pop_previous_day_df_dict.items():
                daily_df_list = []
                
                for dt, daily_df in daily_df_dict.items():
                    daily_df_list.append(daily_df)
                    
                single_ticker_candle_df = pd.concat(daily_df_list, axis=0)
                ticker_daily_df_list.append(single_ticker_candle_df)
            
            complete_daily_df = pd.concat(ticker_daily_df_list, axis=1)
            complete_daily_df = append_customised_indicator(complete_daily_df)
            
            analyse_small_cap_pop(complete_minute_df, complete_daily_df)
            analyse_small_cap_ramp_up(complete_minute_df, complete_daily_df)
            analyse_yesterday_bullish_daily_candle(complete_minute_df, complete_daily_df)
            
            self.initialise()
            print(f'clientID: {self.clientId}, completed top gainer minute candle start: {complete_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_minute_df.iloc[[-1]].index.to_list()[0]}')
            print(f'clientID: {self.clientId}, completed top gainer daily candle range: {complete_daily_df.index.tolist()}')
            print(f'clientID: {self.clientId}, complete top gainer data analysis')
            
            self.data_finished.set()
            
            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_daily_df)
    
    def scannerData(self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr):
        #print(f"scannerData. reqId: {reqId}, rank: {rank}, contractDetails: {contractDetails}, distance: {distance}, benchmark: {benchmark}, projection: {projection}, legsStr: {legsStr}.")
        if re.match('^[a-zA-Z]{1,4}$', contractDetails.contract.symbol): 
            self.small_cap_pop_contract_list.append(contractDetails.contract)
        
    def scannerDataEnd(self, reqId):
        print(f'clientID:{self.clientId}, scanner data end list: {[contract.symbol for contract in self.small_cap_pop_contract_list]}')
        #logger.log_debug_msg(f'clientID:{self.clientId}, scanner data end list: {[contract.symbol for contract in self.small_cap_pop_contract_list]}')
        
        self.screener_finished.set()
          