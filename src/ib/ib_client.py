
import datetime
import re
import pandas as pd

from ibapi.client import *
from ibapi.wrapper import *

from discord.discord_client import send_message, MAIN_BOT
from exception.connection_exception import ConnectionException

from utils.dataframe_util import append_customised_indicator
from utils.logger import Logger

logger = Logger()

class IBClient(EClient, EWrapper):
    small_cap_pop_contract_list = []
    small_cap_pop_df_dict = {}
    small_cap_pop_previous_day_df_dict = {}
    small_cap_pop_minute_df = None
    small_cap_pop_daily_df = None
    nq_minute_df = None
    nq_daily_df = None
    es_minute_df = None
    es_daily_df = None
    ym_minute_df = None
    ym_daily_df = None
    nq_futures_df_dict = {}
    es_futures_df_dict = {}
    ym_futures_df_dict = {}
    nq_futures_previous_day_df_dict = {}
    es_futures_previous_day_df_dict = {}
    ym_futures_previous_day_df_dict = {}
    
    def __init__(self):
        EClient.__init__(self, self)
     
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
            if errorCode == -1:
                connect_fail_msg = f'reqId: {reqId}, TWS Connection Error, errorCode: {errorCode}, message: {errorString}'
                raise ConnectionException(connect_fail_msg)

            if errorCode == 162:
                print(f'cancel TWS scanner subscription, reqId: {reqId}')
                logger.log_debug_msg(f'cancel TWS scanner subscription, reqId: {reqId}')
                self.cancelScannerSubscription(reqId)
            
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
        
        if reqId == 10000:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['NQ'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.nq_futures_df_dict[formated_dt] = single_ticker_candle_df 
            
        if reqId == 11000:
            formated_dt = datetime.datetime.strptime(dt, '%Y%m%d').strftime('%Y-%m-%d')
            
            ohlcv_list = []
            ohlcv_list.append([open, high, low, close, volume])
            ticker_to_indicator_column = pd.MultiIndex.from_product([['NQ'], ['Open', 'High', 'Low', 'Close', 'Volume']])
            single_ticker_candle_df = pd.DataFrame(ohlcv_list, columns=ticker_to_indicator_column, index=[formated_dt])
            self.nq_futures_previous_day_df_dict[formated_dt] = single_ticker_candle_df
            
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
        if 100 <= reqId < 200:
            print(f'{self.small_cap_pop_contract_list[reqId - 100].symbol} minute candle, start: {start}, end: {end}') 
        
        if 200 <= reqId < 300:
            print(f'{self.small_cap_pop_contract_list[reqId - 200].symbol} daily candle, start: {start}, end: {end}') 
        
        if reqId == 10000:
            print(f'NQ minute candle, start: {start}, end: {end}') 
        if reqId == 11000:
            print(f'NQ daily candle, start: {start}, end: {end}') 
        if reqId == 20000:
            print(f'ES minute candle, start: {start}, end: {end}') 
        if reqId == 21000:
            print(f'ES daily candle, start: {start}, end: {end}') 
        if reqId == 30000:
            print(f'YM minute candle, start: {start}, end: {end}') 
        if reqId == 31000:
            print(f'YM daily candle, start: {start}, end: {end}') 
            
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
                ticker_minute_df_list.append(single_ticker_minute_df)
            
            complete_minute_df = pd.concat(ticker_minute_df_list, axis=1)
            complete_minute_df = append_customised_indicator(complete_minute_df)
            
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
            
            print(f'completed minute df first index: {complete_minute_df.index.tolist()[0]}, last index: {complete_minute_df.index.tolist()[-1]}')
            print(f'completed daily df indice: {complete_daily_df.index.tolist()}')

            self.small_cap_pop_minute_df = complete_minute_df
            self.small_cap_pop_daily_df = complete_daily_df
            
            # #debug
            # with pd.option_context('display.max_rows', None,
            #                            'display.max_columns', None,
            #                         'display.precision', 3):
            #     logger.log_debug_msg(complete_daily_df)
            
        if self.nq_futures_df_dict and self.nq_futures_previous_day_df_dict:
            nq_minute_df_list = []
            nq_daily_df_list = []
            
            for dt, nq_minute_df in self.nq_futures_df_dict.items():
                nq_minute_df_list.append(nq_minute_df)
            
            concat_nq_minute_df = pd.concat(nq_minute_df_list, axis=0)
            
            for dt, nq_daily_df in self.nq_futures_previous_day_df_dict.items():
                nq_daily_df_list.append(nq_daily_df)
                
            concat_nq_daily_df = pd.concat(nq_daily_df_list, axis=0)
            complete_nq_minute_df = append_customised_indicator(concat_nq_minute_df)
            complete_nq_daily_df = append_customised_indicator(concat_nq_daily_df)
            
            self.nq_minute_df = complete_nq_minute_df
            self.nq_daily_df = complete_nq_daily_df
            
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
            
        if self.es_futures_df_dict and self.es_futures_previous_day_df_dict:
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
            
            self.es_minute_df = complete_es_minute_df
            self.es_daily_df = complete_es_daily_df
            
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
            
            self.ym_minute_df = complete_ym_minute_df
            self.ym_daily_df = complete_ym_daily_df
            
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
        small_cap_pop_minute_df_size = 0
        small_cap_pop_daily_df_size = 0
        
        if self.small_cap_pop_minute_df is not None and not self.small_cap_pop_minute_df.empty:
            small_cap_pop_minute_df_size = len(list(set(self.small_cap_pop_minute_df.columns.get_level_values(0).tolist())))
        if self.small_cap_pop_daily_df is not None and not self.small_cap_pop_daily_df.empty:
            small_cap_pop_daily_df_size = len(list(set(self.small_cap_pop_daily_df.columns.get_level_values(0).tolist())))
        
        if (
             (((self.small_cap_pop_minute_df is not None and not self.small_cap_pop_minute_df.empty) and
                (self.small_cap_pop_daily_df is not None and not self.small_cap_pop_daily_df.empty) and 
                len(self.small_cap_pop_contract_list) > 0 
                and len(self.small_cap_pop_contract_list) == small_cap_pop_minute_df_size
                and len(self.small_cap_pop_contract_list) == small_cap_pop_daily_df_size)
                 or 
                    (len(self.small_cap_pop_contract_list) == 0)) and
            (self.nq_minute_df is not None and not self.nq_minute_df.empty) and
            (self.nq_daily_df is not None and not self.nq_daily_df.empty) and
            (self.es_minute_df is not None and not self.es_minute_df.empty) and
            (self.es_daily_df is not None and not self.es_daily_df.empty) and
            (self.ym_minute_df is not None and not self.ym_minute_df.empty) and
            (self.ym_daily_df is not None and not self.ym_daily_df.empty)):
                print('disconnect after candle data retrieval')
                self.disconnect()
        
    def scannerData(self, reqId, rank, contractDetails, distance, benchmark, projection, legsStr):
        # print(f"scannerData. reqId: {reqId}, rank: {rank}, contractDetails: {contractDetails}, distance: {distance}, benchmark: {benchmark}, projection: {projection}, legsStr: {legsStr}.")
        if re.match('^[a-zA-Z]{1,4}$', contractDetails.contract.symbol): 
            self.small_cap_pop_contract_list.append(contractDetails.contract)
        
    def scannerDataEnd(self, reqId):
        print(f'scanner data end list: {[contract.symbol for contract in self.small_cap_pop_contract_list]}')
        logger.log_debug_msg(f'scanner data end list: {[contract.symbol for contract in self.small_cap_pop_contract_list]}')
        
        self.cancelScannerSubscription(reqId)
        self.disconnect()
          