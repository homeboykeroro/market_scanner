import datetime
import threading
import pandas as pd

from ibapi.client import *
from ibapi.wrapper import *

from exception.connection_exception import ConnectionException

from utils.dataframe_util import append_customised_indicator
from pattern.indice_pop import analyse_index_pop
from utils.logger import Logger

#logger = Logger('sp500')

class SP500IndexData(EClient, EWrapper):
    es_futures_df_dict = {}
    es_futures_previous_day_df_dict = {}
    minute_data_fetched = False
    daily_data_fetched = False
    
    def __init__(self):
        EClient.__init__(self, self)
        self.data_finished = threading.Event() 
        
    def initialise(self):
        self.es_futures_df_dict = {}
        self.es_futures_previous_day_df_dict = {}
        self.minute_data_fetched = False
        self.daily_data_fetched = False
        
    # def connectAck(self):
    #     print(f'Connecting and fetching S&P500 index data, client id: {self.clientId}')
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

        if reqId == 20000:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['ES'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.es_futures_df_dict[formated_dt] = single_ticker_candle_df 
            
        if reqId == 21000:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d').strftime('%Y-%m-%d')
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['ES'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.es_futures_previous_day_df_dict[formated_dt] = single_ticker_candle_df
            
    #Marks the ending of historical bars reception.
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        if reqId == 20000:
            print(f'clientID: {self.clientId}, ES minute candle, start: {start}, end: {end}') 
            #logger.log_debug_msg(f'clientID: {self.clientId}, ES minute candle, start: {start}, end: {end}')
            self.minute_data_fetched = True
        if reqId == 21000:
            print(f'clientID: {self.clientId}, ES daily candle, start: {start}, end: {end}') 
            #logger.log_debug_msg(f'clientID: {self.clientId}, ES daily candle, start: {start}, end: {end}')
            self.daily_data_fetched = True
            
        if self.minute_data_fetched and self.daily_data_fetched:
            es_minute_df_list = []
            es_daily_df_list = []
            
            for dt, es_minute_df in self.es_futures_df_dict.items():
                es_minute_df_list.append(es_minute_df)
            
            concat_es_minute_df = pd.concat(es_minute_df_list, axis=0)
            
            for dt, es_daily_df in self.es_futures_previous_day_df_dict.items():
                es_daily_df_list.append(es_daily_df)
                
            concat_es_daily_df = pd.concat(es_daily_df_list, axis=0)
            complete_es_minute_df = append_customised_indicator(concat_es_minute_df)
            complete_es_daily_df = append_customised_indicator(concat_es_daily_df)
            analyse_index_pop(complete_es_minute_df, complete_es_daily_df, 'ES')
            self.initialise()
            print(f'clientID: {self.clientId}, completed ES minute candle start: {complete_es_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_es_minute_df.iloc[[-1]].index.to_list()[0]}')
            print(f'clientID: {self.clientId}, completed ES daily candle start: {complete_es_daily_df.index.tolist()}')
            print(f'clientID: {self.clientId}, complete ES data analysis')
            #logger.log_debug_msg(f'clientID: {self.clientId}, completed ES minute candle start: {complete_es_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_es_minute_df.iloc[[-1]].index.to_list()[0]}')
            #logger.log_debug_msg(f'clientID: {self.clientId}, completed ES daily candle start: {complete_es_daily_df.index.tolist()}')
            #logger.log_debug_msg(f'clientID: {self.clientId}, complete ES data analysis')
            #self.cancelHistoricalData(20000)
            #self.cancelHistoricalData(21000)
            
            self.data_finished.set()
            
            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_es_minute_df)
            
            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_es_daily_df)
