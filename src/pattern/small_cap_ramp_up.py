import datetime
import time
import pandas as pd
import pytz

from discord.discord_client import send_message, SMALL_CAP_RAMP_UP
from utils.datetime_util import convert_into_human_readable_time, convert_into_read_out_time
from utils.dataframe_util import derive_idx_df, get_ticker_to_occurrence_idx_list
from utils.logger import Logger

from database.sqlite_connector import execute_in_transaction

idx = pd.IndexSlice
logger = Logger()

MIN_MARUBOZU_RATIO = 40
MIN_CLOSE_PCT = 4
MIN_MA_VOLUME = 3000
HIT_SCANNER_VALID_PERIOD_IN_MIN = 5
        
def analyse_small_cap_ramp_up(minute_df, daily_df):
    analyse_start_time = time.time()
    
    us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
    previous_day_df = daily_df.iloc[[0]] if us_current_datetime.time() < datetime.time(16, 0, 0) else daily_df.iloc[[-1]]
    print(f'Analyse small cap pop ramp up previous day value: {previous_day_df.iloc[[0]].index[-1]}')
    
    close_pct_df = minute_df.loc[:, idx[:, 'Close Change%']].rename(columns={'Close Change%': 'Compare'})
    previous_close_df = previous_day_df.loc[:, idx[:, 'Close']] 
    previous_close_pct_df = (((minute_df.loc[:, idx[:, 'Close']].sub(previous_close_df.values))
                                                                .div(previous_close_df.values))
                                                                .mul(100)).rename(columns={'Close': 'Close Change%'})
    
    candle_colour_df = minute_df.loc[:, idx[:, 'Candle Colour']].rename(columns={'Candle Colour': 'Compare'})
    marubozu_ratio_df = minute_df.loc[:, idx[:, 'Marubozu Ratio']].rename(columns={'Marubozu Ratio': 'Compare'})
    
    volume_df = minute_df.loc[:, idx[:, 'Volume']].rename(columns={'Volume': 'Compare'})
    vol_20_ma_df = minute_df.loc[:, idx[:, '20MA Volume']].rename(columns={'20MA Volume': 'Compare'})
    vol_50_ma_df = minute_df.loc[:, idx[:, '50MA Volume']].rename(columns={'50MA Volume': 'Compare'})
    
    green_candle_df = (candle_colour_df == 'GREEN')
    marubozu_boolean_df = (marubozu_ratio_df >= MIN_MARUBOZU_RATIO)
    candle_close_pct_boolean_df = (close_pct_df >= MIN_CLOSE_PCT)
    above_vol_20_ma_boolean_df = (volume_df >= vol_20_ma_df) & (vol_20_ma_df >= MIN_MA_VOLUME)
    above_vol_50_ma_boolean_df = (volume_df >= vol_50_ma_df) & (vol_50_ma_df >= MIN_MA_VOLUME)
    
    ramp_up_boolean_df = (green_candle_df) & (marubozu_boolean_df) & (candle_close_pct_boolean_df)
    ma_20_ramp_up_boolean_df = (above_vol_20_ma_boolean_df) & (ramp_up_boolean_df)
    ma_50_ramp_up_boolean_df = (above_vol_50_ma_boolean_df) & (ramp_up_boolean_df)
    
    ticker_to_ma_20_occurrence_idx_list_dict = get_ticker_to_occurrence_idx_list(ma_20_ramp_up_boolean_df)
    ticker_to_ma_50_occurrence_idx_list_dict = get_ticker_to_occurrence_idx_list(ma_50_ramp_up_boolean_df)
    
    above_vol_20_ma_result_series = ma_20_ramp_up_boolean_df.any()
    above_vol_20_ma_ticker_list = above_vol_20_ma_result_series.index[above_vol_20_ma_result_series].get_level_values(0).tolist()
    
    above_vol_50_ma_result_series = ma_50_ramp_up_boolean_df.any()
    above_vol_50_ma_ticker_list = above_vol_50_ma_result_series.index[above_vol_50_ma_result_series].get_level_values(0).tolist()
    
    if len(above_vol_50_ma_ticker_list) > 0:
        ma_50_ramp_up_readout_message_list = []
        ma_50_ramp_up_display_message_list = []
        ma_50_ramp_up_save_db_params_list = []
        
        for ticker in above_vol_50_ma_ticker_list:
            occurrence_idx_list = ticker_to_ma_50_occurrence_idx_list_dict[ticker]

            for occurrence_idx in occurrence_idx_list:   
                if not occurrence_idx:
                    continue
        
                us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
                current_datetime_and_ramp_up_time_diff = int(((us_current_datetime.replace(tzinfo=None) - datetime.datetime.strptime(occurrence_idx, '%Y-%m-%d %H:%M:%S')).total_seconds()) / 60)
                
                if current_datetime_and_ramp_up_time_diff <= HIT_SCANNER_VALID_PERIOD_IN_MIN:
                    record_exist_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                      WHERE TICKER = ? 
                                                      AND HIT_SCANNER_DATETIME = ? 
                                                      AND SCAN_PATTERN = ? 
                                                      AND BAR_SIZE = ?""",
                                                    (ticker, occurrence_idx, 'SMALL_CAP_RAMP_UP', '1min'))
                    record_count = dict(record_exist_result[0])['ct']
                    
                    notify = (record_count == 0)
                    
                    if notify:
                        close = float(minute_df.loc[occurrence_idx, (ticker, 'Close')])
                        close_pct = float(minute_df.loc[occurrence_idx, (ticker, 'Close Change%')])
                        previous_close_pct = previous_close_pct_df.loc[occurrence_idx, (ticker, 'Close Change%')]
                        volume = int(minute_df.loc[occurrence_idx, (ticker, 'Volume')])
                        ma_50_volume = int(minute_df.loc[occurrence_idx, (ticker, '50MA Volume')])
                        total_volume = int(minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
                        
                        #debug [-1] -> [0] 
                        yesterday_close = float(previous_day_df.loc[previous_day_df.index[-1], (ticker, 'Close')])
                        
                        hit_scanner_datetime_display = convert_into_human_readable_time(occurrence_idx)
                        read_out_pop_up_time = convert_into_read_out_time(occurrence_idx)
                        
                        readout_message = f'{" ".join(ticker)} ramp up {round(close_pct, 2)}% at {read_out_pop_up_time}'
                        display_message = f'{ticker} ramp up {round(close_pct, 2)}% at {hit_scanner_datetime_display}, close: {close}, previous close: {yesterday_close}, previous day percent change: {round(previous_close_pct, 2)}, volume: {volume:,.2f}, 50MA volume: {ma_50_volume}, total volume: {total_volume:,.2f}'
                        ma_50_ramp_up_readout_message_list.append(readout_message)
                        ma_50_ramp_up_display_message_list.append(display_message)
                        ma_50_ramp_up_save_db_params_list.append((ticker, occurrence_idx))
                        print(f'${ticker} small cap 50MA volume ramp up, hit scanner datetime: {occurrence_idx}')
                        
        send_message_time = time.time()
        if len(ma_50_ramp_up_readout_message_list) > 0:
            for pos, readout_message in enumerate(ma_50_ramp_up_readout_message_list):
                display_message = ma_50_ramp_up_display_message_list[pos]
                send_message(channel=SMALL_CAP_RAMP_UP, message=readout_message, tts=True)
                send_message(channel=SMALL_CAP_RAMP_UP, message=display_message, tts=False)
                
                save_ticker = ma_50_ramp_up_save_db_params_list[pos][0]
                save_hit_scanner_datetime = ma_50_ramp_up_save_db_params_list[pos][1]
                execute_in_transaction("""INSERT INTO PATTERN_ANALYSIS 
                                        (TICKER, HIT_SCANNER_DATETIME, SCAN_PATTERN, BAR_SIZE) 
                                        VALUES (?, ?, ?, ?)""",
                                        (save_ticker, save_hit_scanner_datetime, 'SMALL_CAP_RAMP_UP', '1min'))
        print(f'Small cap 50MA volume ramp up send message time: {time.time() - send_message_time} seconds')
    
    if len(above_vol_20_ma_ticker_list) > 0:
        ma_20_ramp_up_readout_message_list = []
        ma_20_ramp_up_display_message_list = []
        ma_20_ramp_up_save_db_params_list = []
        
        for ticker in above_vol_20_ma_ticker_list:
            occurrence_idx_list = ticker_to_ma_20_occurrence_idx_list_dict[ticker]

            for occurrence_idx in occurrence_idx_list:   
                if not occurrence_idx:
                    continue
        
                us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
                current_datetime_and_ramp_up_time_diff = int(((us_current_datetime.replace(tzinfo=None) - datetime.datetime.strptime(occurrence_idx, '%Y-%m-%d %H:%M:%S')).total_seconds()) / 60)
                
                if current_datetime_and_ramp_up_time_diff <= HIT_SCANNER_VALID_PERIOD_IN_MIN:
                    record_exist_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                      WHERE TICKER = ? 
                                                      AND HIT_SCANNER_DATETIME = ? 
                                                      AND SCAN_PATTERN = ? 
                                                      AND BAR_SIZE = ?""",
                                                    (ticker, occurrence_idx, 'SMALL_CAP_RAMP_UP', '1min'))
                    record_count = dict(record_exist_result[0])['ct']
                    
                    notify = (record_count == 0)
                    
                    if notify:
                        close = float(minute_df.loc[occurrence_idx, (ticker, 'Close')])
                        close_pct = float(minute_df.loc[occurrence_idx, (ticker, 'Close Change%')])
                        previous_close_pct = previous_close_pct_df.loc[occurrence_idx, (ticker, 'Close Change%')]
                        volume = int(minute_df.loc[occurrence_idx, (ticker, 'Volume')])
                        ma_20_volume = int(minute_df.loc[occurrence_idx, (ticker, '20MA Volume')])
                        total_volume = int(minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
                        
                        #debug [-1] -> [0] 
                        yesterday_close = float(previous_day_df.loc[previous_day_df.index[-1], (ticker, 'Close')])
                        
                        hit_scanner_datetime_display = convert_into_human_readable_time(occurrence_idx)
                        read_out_pop_up_time = convert_into_read_out_time(occurrence_idx)
                        
                        readout_message = f'{" ".join(ticker)} ramp up {round(close_pct, 2)}% at {read_out_pop_up_time}'
                        display_message = f'{ticker} ramp up {round(close_pct, 2)}% at {hit_scanner_datetime_display}, close: {close}, previous close: {yesterday_close}, previous day percent change: {round(previous_close_pct, 2)}, volume: {volume:,.2f}, 20MA volume: {ma_20_volume}, total volume: {total_volume:,.2f}'
                        ma_20_ramp_up_readout_message_list.append(readout_message)
                        ma_20_ramp_up_display_message_list.append(display_message)
                        ma_20_ramp_up_save_db_params_list.append((ticker, occurrence_idx))
                        print(f'${ticker} small cap 20MA volume ramp up, hit scanner datetime: {occurrence_idx}')

        send_message_time = time.time()
        if len(ma_20_ramp_up_readout_message_list) > 0:
            for pos, readout_message in enumerate(ma_20_ramp_up_readout_message_list):
                display_message = ma_20_ramp_up_display_message_list[pos]
                send_message(channel=SMALL_CAP_RAMP_UP, message=readout_message, tts=True)
                send_message(channel=SMALL_CAP_RAMP_UP, message=display_message, tts=False)
                
                save_ticker = ma_20_ramp_up_save_db_params_list[pos][0]
                save_hit_scanner_datetime = ma_20_ramp_up_save_db_params_list[pos][1]
                execute_in_transaction("""INSERT INTO PATTERN_ANALYSIS 
                                        (TICKER, HIT_SCANNER_DATETIME, SCAN_PATTERN, BAR_SIZE) 
                                        VALUES (?, ?, ?, ?)""",
                                        (save_ticker, save_hit_scanner_datetime, 'SMALL_CAP_RAMP_UP', '1min'))
        print(f'Small cap 20MA volume ramp up send message time: {time.time() - send_message_time} seconds')
    
    
    