
import datetime
import threading
import pandas as pd

from ibapi.client import *
from ibapi.wrapper import *

from exception.connection_exception import ConnectionException

from utils.dataframe_util import append_customised_indicator
from pattern.indice_pop import analyse_index_pop
from utils.logger import Logger

logger = Logger()

class DowJonesIndexData(EClient, EWrapper):
    ym_futures_df_dict = {}
    ym_futures_previous_day_df_dict = {}
    
    def __init__(self):
        EClient.__init__(self, self)
        
    def initialise(self):
        self.ym_futures_df_dict = {}
        self.ym_futures_previous_day_df_dict = {}

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
            if errorCode == -1:
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
        
        if reqId == 30000:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['YM'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.ym_futures_df_dict[formated_dt] = single_ticker_candle_df 
            
        if reqId == 31000:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d').strftime('%Y-%m-%d')
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['YM'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.ym_futures_previous_day_df_dict[formated_dt] = single_ticker_candle_df
            
    #Marks the ending of historical bars reception.
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        if reqId == 30000:
            print(f'{threading.current_thread().name} YM minute candle, start: {start}, end: {end}') 
        if reqId == 31000:
            print(f'{threading.current_thread().name} YM daily candle, start: {start}, end: {end}') 
        
        if self.ym_futures_df_dict and self.ym_futures_previous_day_df_dict:
            ym_minute_df_list = []
            ym_daily_df_list = []
            
            for dt, ym_minute_df in self.ym_futures_df_dict.items():
                ym_minute_df_list.append(ym_minute_df)
            
            concat_ym_minute_df = pd.concat(ym_minute_df_list, axis=0)
            
            for dt, ym_daily_df in self.ym_futures_previous_day_df_dict.items():
                ym_daily_df_list.append(ym_daily_df)
                
            concat_ym_daily_df = pd.concat(ym_daily_df_list, axis=0)
            complete_ym_minute_df = append_customised_indicator(concat_ym_minute_df)
            complete_ym_daily_df = append_customised_indicator(concat_ym_daily_df)
            analyse_index_pop(complete_ym_minute_df, complete_ym_daily_df, 'YM')
            self.initialise()
            #self.cancelHistoricalData(reqId)

            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_ym_minute_df)
            
            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_ym_daily_df)
            
        
          