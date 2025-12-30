import datetime
import threading
import pandas as pd
import pytz

from ibapi.client import *
from ibapi.wrapper import *

from exception.connection_exception import ConnectionException

from utils.dataframe_util import append_customised_indicator
from utils.datetime_util import convert_to_eastern
from pattern.indice_pop import analyse_index_pop
from pattern.indice_dip import analyse_index_dip
#from utils.logger import Logger

#logger = Logger('nasdaq')

class NasdaqIndexData(EClient, EWrapper):
    nq_futures_df_dict = {}
    nq_futures_previous_day_df_dict = {}
    minute_data_fetched = False
    daily_data_fetched = False
    
    def __init__(self):
        EClient.__init__(self, self)
        self.initialise()
        self.data_finished = threading.Event() 
        
    def initialise(self):
        self.nq_futures_df_dict = {}
        self.nq_futures_previous_day_df_dict = {}
        self.minute_data_fetched = False
        self.daily_data_fetched = False
        
    # def connectAck(self):
    #     print(f'Connecting and fetching Nasdaq index data, client id: {self.clientId}')
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
            print(bypass_error_msg)
        elif errorCode in connection_error_code_list:
            connect_fail_msg = f'reqId: {reqId}, TWS Connection Error, errorCode: {errorCode}, message: {errorString}'
            raise ConnectionException(connect_fail_msg)
        else:
            #438 - application is locked
            if errorCode == -1 or errorCode == 502 or errorCode == 504 or errorCode == 438:
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
        
        if 'US/Central' in bar.date or 'US/Eastern' in bar.date:
            dt = convert_to_eastern(bar.date)
            dt = dt.replace(" US/Eastern", "")
        else:
            dt = datetime.datetime.strptime(bar.date, '%Y%m%d').strftime('%Y-%m-%d')
            
        if reqId == 10000:
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['NQ'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[dt])
            self.nq_futures_df_dict[dt] = single_ticker_candle_df 
            
        if reqId == 11000:
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['NQ'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[dt])
            self.nq_futures_previous_day_df_dict[dt] = single_ticker_candle_df
            
    #Marks the ending of historical bars reception.
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        if reqId == 10000:
            print(f'clientID: {self.clientId}, NQ minute candle, start: {start}, end: {end}') 
            #logger.log_debug_msg(f'clientID: {self.clientId}, NQ minute candle, start: {start}, end: {end}')
            self.minute_data_fetched = True
        if reqId == 11000:
            print(f'clientID: {self.clientId}, NQ daily candle, start: {start}, end: {end}') 
            #logger.log_debug_msg(f'clientID: {self.clientId}, NQ daily candle, start: {start}, end: {end}')
            self.daily_data_fetched = True
            
        us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
        premarket_start_time = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0) if datetime.time(0, 0, 0) < us_current_datetime.time() < datetime.time(4, 0, 0) else us_current_datetime.replace(hour=4, minute=0, second=0)
        premarket_start_time = premarket_start_time.strftime('%Y-%m-%d %H:%M:%S')
        
        if self.minute_data_fetched and self.daily_data_fetched:
            nq_minute_df_list = []
            nq_daily_df_list = []
            
            for dt, nq_minute_df in self.nq_futures_df_dict.items():
                nq_minute_df_list.append(nq_minute_df)
            
            concat_nq_minute_df = pd.concat(nq_minute_df_list, axis=0)
            concat_nq_minute_df = concat_nq_minute_df.loc[premarket_start_time:, :]
            print(f'NQ futures concat minute candle start datetime: {concat_nq_minute_df.iloc[[0]].index[0]}, end datetime: {concat_nq_minute_df.iloc[[-1]].index[0]}')
            
            for dt, nq_daily_df in self.nq_futures_previous_day_df_dict.items():
                nq_daily_df_list.append(nq_daily_df)
                
            concat_nq_daily_df = pd.concat(nq_daily_df_list, axis=0)
            complete_nq_minute_df = append_customised_indicator(concat_nq_minute_df)
            complete_nq_daily_df = append_customised_indicator(concat_nq_daily_df)
            analyse_index_pop(complete_nq_minute_df, complete_nq_daily_df, 'NQ')
            analyse_index_dip(complete_nq_minute_df, complete_nq_daily_df, 'NQ')
            self.initialise()
            print(f'clientID: {self.clientId}, completed NQ minute candle start: {complete_nq_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_nq_minute_df.iloc[[-1]].index.to_list()[0]}')
            print(f'clientID: {self.clientId}, completed NQ daily candle range: {complete_nq_daily_df.index.tolist()}')
            print(f'clientID: {self.clientId}, complete NQ data analysis')
            #logger.log_debug_msg(f'clientID: {self.clientId}, completed NQ minute candle start: {complete_nq_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_nq_minute_df.iloc[[-1]].index.to_list()[0]}')
            #logger.log_debug_msg(f'clientID: {self.clientId}, completed NQ daily candle start: {complete_nq_daily_df.index.tolist()}')
            #logger.log_debug_msg(f'clientID: {self.clientId}, complete NQ data analysis')
            #self.cancelHistoricalData(10000)
            #self.cancelHistoricalData(11000)

            self.data_finished.set()

            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_nq_minute_df)
            
            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_nq_daily_df)
