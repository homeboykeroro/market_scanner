import datetime
import threading
import traceback
import pandas as pd
import pytz

from ibapi.client import *
from ibapi.wrapper import *

from exception.connection_exception import ConnectionException

from utils.dataframe_util import append_customised_indicator
from utils.datetime_util import convert_to_eastern, get_us_business_day
from pattern.indice_pop import analyse_index_pop
from pattern.indice_dip import analyse_index_dip
#from utils.logger import Logger

#logger = Logger()

class DowJonesIndexData(EClient, EWrapper):
    ym_futures_df_dict = {}
    ym_futures_previous_day_df_dict = {}
    minute_data_fetched = False
    daily_data_fetched = False
    error_list = []
    
    def __init__(self):
        EClient.__init__(self, self)
        self.initialise()
        self.data_finished = threading.Event() 
        
    def initialise(self):
        self.ym_futures_df_dict = {}
        self.ym_futures_previous_day_df_dict = {}
        self.minute_data_fetched = False
        self.daily_data_fetched = False
        self.error_list = []
        
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
            exception_obj = ConnectionException(connect_fail_msg)
            self.error_list.append(exception_obj)
        else:
            #438 - application is locked
            if errorCode == -1 or errorCode == 502 or errorCode == 504 or errorCode == 438:
                connect_fail_msg = f'reqId: {reqId}, TWS Connection Error, errorCode: {errorCode}, message: {errorString}'
                exception_obj =  ConnectionException(connect_fail_msg)
                self.error_list.append(exception_obj)
            else:
                fatal_error_msg = f'reqId: {reqId}, TWS Fatal Error, errorCode: {errorCode}, message: {errorString}'
                exception_obj = Exception(fatal_error_msg)
                self.error_list.append(exception_obj)
        
        if len(self.error_list) > 0:
            self.data_finished.set()

    def headTimestamp(self, reqId:int, headTimestamp:str):
        print("HeadTimestamp. reqId:", reqId, "headTimeStamp:", headTimestamp)

    def historicalData(self, reqId: int, bar: BarData):
        try:
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

            if reqId == 30000:
                ohlcv_list = []
                ohlcv_list.append([open, high, low, close, volume])
                ticker_to_indicator_column = pd.MultiIndex.from_product([['YM'], ['Open', 'High', 'Low', 'Close', 'Volume']])
                single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[dt])
                self.ym_futures_df_dict[dt] = single_ticker_candle_df 

            if reqId == 31000:
                ohlcv_list = []
                ohlcv_list.append([open, high, low, close, volume])
                ticker_to_indicator_column = pd.MultiIndex.from_product([['YM'], ['Open', 'High', 'Low', 'Close', 'Volume']])
                single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[dt])
                self.ym_futures_previous_day_df_dict[dt] = single_ticker_candle_df
        except Exception as e:
            print(traceback.format_exc())
            self.error_list.append(e)
            self.data_finished.set()

    #Marks the ending of historical bars reception.
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        try:
            if reqId == 30000:
                print(f'clientID: {self.clientId}, YM minute candle, start: {start}, end: {end}')
                #logger.log_debug_msg(f'clientID: {self.clientId}, YM minute candle, start: {start}, end: {end}')
                self.minute_data_fetched = True
            if reqId == 31000:
                print(f'clientID: {self.clientId}, YM daily candle, start: {start}, end: {end}') 
                #logger.log_debug_msg(f'clientID: {self.clientId}, YM daily candle, start: {start}, end: {end}')
                self.daily_data_fetched = True

            us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
            previous_us_business_day = get_us_business_day(-1, us_current_datetime)
            nearest_trading_day = get_us_business_day(0, us_current_datetime)

            if self.minute_data_fetched and self.daily_data_fetched:
                if (datetime.time(16, 0, 0) <= us_current_datetime.time().replace(microsecond=0) <= datetime.time(23, 59, 59)):
                    if us_current_datetime.weekday() == 6:
                        start_range = previous_us_business_day.replace(hour=16, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        start_range = nearest_trading_day.replace(hour=16, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                elif datetime.time(0, 0, 0) <= us_current_datetime.time().replace(microsecond=0) < datetime.time(4, 0, 0):
                    start_range = previous_us_business_day.replace(hour=16, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                elif datetime.time(4, 0, 0) <= us_current_datetime.time().replace(microsecond=0) < datetime.time(16, 0, 0):
                    start_range = nearest_trading_day.replace(hour=4, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')

                print(f'Slice YM minute candle start range: {start_range}')

                ym_minute_df_list = []
                ym_daily_df_list = []

                for dt, ym_minute_df in self.ym_futures_df_dict.items():
                    ym_minute_df_list.append(ym_minute_df)

                concat_ym_minute_df = pd.concat(ym_minute_df_list, axis=0)
                print(f'YM original concat minute candle start datetime: {concat_ym_minute_df.iloc[[0]].index[0]}, end datetime: {concat_ym_minute_df.iloc[[-1]].index[0]}')
                concat_ym_minute_df = concat_ym_minute_df.loc[start_range:, :]
                
                if concat_ym_minute_df is None or concat_ym_minute_df.empty:
                    print(f'Empty YM minute dataframe')
                    self.data_finished.set()
                    return
                print(f'YM sliced concat minute candle start datetime: {concat_ym_minute_df.iloc[[0]].index[0]}, end datetime: {concat_ym_minute_df.iloc[[-1]].index[0]}')

                for dt, ym_daily_df in self.ym_futures_previous_day_df_dict.items():
                    ym_daily_df_list.append(ym_daily_df)

                concat_ym_daily_df = pd.concat(ym_daily_df_list, axis=0)

                complete_ym_minute_df = append_customised_indicator(concat_ym_minute_df)
                complete_ym_daily_df = append_customised_indicator(concat_ym_daily_df)
                analyse_index_pop(complete_ym_minute_df, complete_ym_daily_df, 'YM')
                analyse_index_dip(complete_ym_minute_df, complete_ym_daily_df, 'YM')
                self.initialise()
                print(f'clientID: {self.clientId}, completed YM minute candle start: {complete_ym_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_ym_minute_df.iloc[[-1]].index.to_list()[0]}')
                print(f'clientID: {self.clientId}, completed YM daily candle range: {complete_ym_daily_df.index.tolist()}')
                print(f'clientID: {self.clientId}, complete YM data analysis')
                #logger.log_debug_msg(f'clientID: {self.clientId}, completed NQ minute candle start: {complete_ym_minute_df.iloc[[0]].index.to_list()[0]}, end: {complete_ym_minute_df.iloc[[-1]].index.to_list()[0]}')
                #logger.log_debug_msg(f'clientID: {self.clientId}, completed NQ daily candle start: {complete_ym_daily_df.index.tolist()}')
                #logger.log_debug_msg(f'clientID: {self.clientId}, complete NQ data analysis')
                #self.cancelHistoricalData(10000)
                #self.cancelHistoricalData(11000)
                self.data_finished.set()

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
        except Exception as e:
            print(traceback.format_exc())
            self.error_list.append(e)
            self.data_finished.set()