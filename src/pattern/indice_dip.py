import datetime
import time
import pandas as pd
import numpy as np
import pytz

from utils.logger import Logger
from utils.dataframe_util import get_ticker_to_occurrence_idx_list
from utils.datetime_util import convert_into_human_readable_time, convert_into_read_out_time

from notification.discord_client import NQ_DIP, NQ_CLOSE_PCT_DOWN, ES_DIP, ES_CLOSE_PCT_DOWN, YM_DIP, YM_CLOSE_PCT_DOWN, GD_DIP, GD_CLOSE_PCT_DOWN, send_message

from database.sqlite_connector import execute_in_transaction

idx = pd.IndexSlice
logger = Logger(filename='nasdaq')
 
MIN_INDEX_CLOSE_PCT = -0.03
INDEX_TOP_N_VOLUME = 10
MIN_MARUBOZU_RATIO = 40
HIT_SCANNER_VALID_PERIOD_IN_MIN = 10

def analyse_index_dip(minute_df, daily_df, index) -> None:
    analyse_start_time = time.time()
    
    candle_colour_df = minute_df.loc[:, idx[:, 'Candle Colour']].rename(columns={'Candle Colour': 'Compare'})
    close_pct_df = minute_df.loc[:, idx[:, 'Close Change%']].rename(columns={'Close Change%': 'Compare'})
    marubozu_ratio_df = minute_df.loc[:, idx[:, 'Marubozu Ratio']].rename(columns={'Marubozu Ratio': 'Compare'})
    
    us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
    if datetime.time(4, 0, 0) <= us_current_datetime.time() < datetime.time(9, 30, 0):
        previous_day_df = daily_df.iloc[[-1]]
    if us_current_datetime.time() >= datetime.time(16, 0, 0):
        previous_day_df = daily_df.iloc[[-1]]
    if (datetime.time(0, 0, 0) <= us_current_datetime.time() < datetime.time(4, 0, 0)):
        previous_day_df = daily_df.iloc[[-1]]
    if datetime.time(9, 30, 0) <= us_current_datetime.time() < datetime.time(16, 0, 0):
        previous_day_df = daily_df.iloc[[0]]
    
    print(f'Analyse {index} index dip previous day value: {previous_day_df.iloc[[0]].index[-1]}')
    
    close_df = minute_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    previous_close_df = previous_day_df.iloc[[0]].loc[:, idx[:, 'Close']]
    previous_close_pct_df = close_df.sub(previous_close_df.values)
    previous_close_pct_df = previous_close_pct_df.div(previous_close_df.values)
    previous_close_pct_df = previous_close_pct_df.mul(100)
    
    #dip (>20ma, >50ma, top 10 volume)
    red_candle_df = (candle_colour_df == 'Red')
    marubozu_boolean_df = (marubozu_ratio_df >= MIN_MARUBOZU_RATIO)
    min_pct_boolean_df = (close_pct_df <= MIN_INDEX_CLOSE_PCT)
    
    volume_df = minute_df.loc[:, idx[:, 'Volume']].rename(columns={'Volume': 'Compare'})
    vol_20_ma_df = minute_df.loc[:, idx[:, '20MA Volume']].rename(columns={'20MA Volume': 'Compare'})
    vol_50_ma_df = minute_df.loc[:, idx[:, '50MA Volume']].rename(columns={'50MA Volume': 'Compare'})
    above_vol_20_ma_boolean_df = (volume_df >= vol_20_ma_df)
    above_vol_50_ma_boolean_df = (volume_df >= vol_50_ma_df)
    index_top_n_volume_np = np.sort(volume_df.fillna(0).astype(int, errors = 'ignore').to_numpy(), axis=0)[::-1][:INDEX_TOP_N_VOLUME, :]  
    is_in_index_top_n_volume = volume_df >= index_top_n_volume_np.min(axis=0)
    top_10_volume_boolean_df = pd.DataFrame(is_in_index_top_n_volume, 
                                            index=volume_df.index, 
                                            columns=volume_df.columns)
    # # #debug
    # logger.log_debug_msg('=======================================')
    # with pd.option_context('display.max_rows', None,
    #                         'display.max_columns', None,
    #                         'display.precision', 3):
    #     logger.log_debug_msg(minute_df)
    # logger.log_debug_msg('---------------------------------------')
    # with pd.option_context('display.max_rows', None,
    #                         'display.max_columns', None,
    #                         'display.precision', 3):
    #     logger.log_debug_msg(daily_df)
    # logger.log_debug_msg('---------------------------------------')
    # with pd.option_context('display.max_rows', None,
    #                         'display.max_columns', None,
    #                         'display.precision', 3):
    #     logger.log_debug_msg(previous_close_pct_df)
    # logger.log_debug_msg('=======================================')
    
    index_dip_boolean_df = (red_candle_df) & (marubozu_boolean_df) & (min_pct_boolean_df) & (above_vol_20_ma_boolean_df | above_vol_50_ma_boolean_df | top_10_volume_boolean_df)

    ticker_to_dip_occurrence_idx_list_dict = get_ticker_to_occurrence_idx_list(index_dip_boolean_df)
    
    index_dip_result_series = index_dip_boolean_df.any()   
    index_dip_ticker_list = index_dip_result_series.index[index_dip_result_series].get_level_values(0).tolist()
    
    if len(index_dip_ticker_list) > 0:
        readout_message_list = []
        display_message_list = []
        save_db_params_list = []
        
        for ticker in index_dip_ticker_list:
            occurrence_idx_list = ticker_to_dip_occurrence_idx_list_dict[ticker]

            for occurrence_idx in occurrence_idx_list:   
                if not occurrence_idx:
                    continue
                
                us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
                current_datetime_and_dip_time_diff = int(((us_current_datetime.replace(tzinfo=None) - datetime.datetime.strptime(occurrence_idx, '%Y-%m-%d %H:%M:%S')).total_seconds()) / 60)

                #debug
                #if True:
                if current_datetime_and_dip_time_diff <= HIT_SCANNER_VALID_PERIOD_IN_MIN:
                    record_exist_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                                  WHERE TICKER = ? 
                                                                  AND HIT_SCANNER_DATETIME = ? 
                                                                  AND SCAN_PATTERN = ? 
                                                                  AND BAR_SIZE = ?""",
                                                                (ticker, occurrence_idx, f'{index}_DIP', '1min'))
                    record_count = dict(record_exist_result[0])['ct']

                    notify = (record_count == 0)

                    if notify:
                        close = float(minute_df.loc[occurrence_idx, (ticker, 'Close')])
                        volume = int(minute_df.loc[occurrence_idx, (ticker, 'Volume')])
                        close_pct = float(minute_df.loc[occurrence_idx, (ticker, 'Close Change%')])
                        total_volume = int(minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
                        ma_20_volume = int(vol_20_ma_df.loc[occurrence_idx, (ticker, 'Compare')])
                        ma_50_volume = int(vol_50_ma_df.loc[occurrence_idx, (ticker, 'Compare')])
                        top_n_volume = index_top_n_volume_np
                        
                        yesterday_close = float(previous_day_df.loc[previous_day_df.index[-1], (ticker, 'Close')])

                        hit_scanner_datetime_display = convert_into_human_readable_time(occurrence_idx)
                        read_out_dip_time = convert_into_read_out_time(occurrence_idx)

                        readout_message = f'{" ".join(ticker)} index dip {round(close_pct, 2)}% at {read_out_dip_time}'
                        display_message = f'{ticker} index dip {round(close_pct, 2)}% at {hit_scanner_datetime_display}, close: {close}, previous close: {yesterday_close}, volume: {volume:,.2f}, total volume: {total_volume:,.2f}, 20MA volume: {ma_20_volume}, 50MA volume: {ma_50_volume}, top N volume: {top_n_volume}'
                        readout_message_list.append(readout_message)
                        display_message_list.append(display_message)
                        save_db_params_list.append((ticker, occurrence_idx))
                        print(f'{index} index dip, hit scanner datetime: {occurrence_idx}')
        
        print(f'{index} index dip analyse time: {time.time() - analyse_start_time} seconds')
        
        if index == 'NQ':
            send_channel = NQ_DIP
        elif index == 'ES':
            send_channel = ES_DIP
        elif index == 'YM':
            send_channel = YM_DIP
        elif index == 'GD':
            send_channel = GD_DIP
        
        send_message_time = time.time()
        if len(readout_message_list) > 0:
            for pos, readout_message in enumerate(readout_message_list):
                display_message = display_message_list[pos]
                send_message(channel=send_channel, message=readout_message, tts=True)
                send_message(channel=send_channel, message=display_message, tts=False)
                
                save_ticker = save_db_params_list[pos][0]
                save_hit_scanner_datetime = save_db_params_list[pos][1]
                execute_in_transaction("""INSERT INTO PATTERN_ANALYSIS 
                                        (TICKER, HIT_SCANNER_DATETIME, SCAN_PATTERN, BAR_SIZE) 
                                        VALUES (?, ?, ?, ?)""",
                                        (save_ticker, save_hit_scanner_datetime, f'{index}_DIP', '1min'))
        print(f'{index} index dip send message time: {time.time() - send_message_time} seconds')
    
    #close percent change notification
    natural_number_close_pct_df = previous_close_pct_df.fillna(999).astype(int, errors = 'ignore')
    natural_number_close_pct_df = natural_number_close_pct_df.where((natural_number_close_pct_df <= 0).values)
    natural_number_close_pct_df = natural_number_close_pct_df.ffill()
    shifted_natural_number_close_pct_df = natural_number_close_pct_df.shift(1)
    progressive_boolean_df = ((natural_number_close_pct_df - shifted_natural_number_close_pct_df) < 0)
    close_pct_cum_max_df = natural_number_close_pct_df.cummax()
    compare_cum_max_boolean_df = (natural_number_close_pct_df >= close_pct_cum_max_df) & (natural_number_close_pct_df != 0)
    hit_scanner_close_pct_boolean_df = (progressive_boolean_df) & (compare_cum_max_boolean_df)
    ticker_to_close_pct_occurrence_idx_list_dict = get_ticker_to_occurrence_idx_list(hit_scanner_close_pct_boolean_df)
    
    index_close_pct_result_series = hit_scanner_close_pct_boolean_df.any()   
    index_close_pct_ticker_list = index_close_pct_result_series.index[index_close_pct_result_series].get_level_values(0).tolist()
    
    if len(index_close_pct_ticker_list) > 0:
        readout_message_list = []
        display_message_list = []
        save_db_params_list = []
    
        for ticker in index_close_pct_ticker_list:
            occurrence_idx_list = ticker_to_close_pct_occurrence_idx_list_dict[ticker]
    
            for occurrence_idx in occurrence_idx_list:   
                if not occurrence_idx:
                    continue
        
                record_exist_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                  WHERE TICKER = ? 
                                                  AND HIT_SCANNER_DATETIME = ? 
                                                  AND SCAN_PATTERN = ? 
                                                  AND BAR_SIZE = ?""",
                                                (ticker, occurrence_idx, f'{index}_CLOSE_PCT_DIP', '1min'))
                record_count = dict(record_exist_result[0])['ct']
    
                notify = (record_count == 0)
    
                if notify:
                    close = float(minute_df.loc[occurrence_idx, (ticker, 'Close')])
                    volume = int(minute_df.loc[occurrence_idx, (ticker, 'Volume')])
                    total_volume = int(minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
    
                    yesterday_close = float(previous_day_df.loc[previous_day_df.index[-1], (ticker, 'Close')])
                    previous_close_pct = round((((close - yesterday_close) / yesterday_close) * 100), 2)
    
                    hit_scanner_datetime_display = convert_into_human_readable_time(occurrence_idx)
                    read_out_dip_time = convert_into_read_out_time(occurrence_idx)
    
                    readout_message = f'{" ".join(ticker)} index reaches {round(previous_close_pct, 2)}% at {read_out_dip_time}'
                    display_message = f'{ticker} index reaches {round(previous_close_pct, 2)}% at {hit_scanner_datetime_display}, close: {close}, previous close: {yesterday_close}, volume: {volume:,.2f}, total volume: {total_volume:,.2f}'
                    readout_message_list.append(readout_message)
                    display_message_list.append(display_message)
                    save_db_params_list.append((ticker, occurrence_idx))
                    print(f'{index} index close pct change dip, hit scanner datetime: {occurrence_idx}')
    
        print(f'{index} close pct dip analyse time: {time.time() - analyse_start_time} seconds')
    
        if index == 'NQ':
            send_channel = NQ_CLOSE_PCT_DOWN
        elif index == 'ES':
            send_channel = ES_CLOSE_PCT_DOWN
        elif index == 'YM':
            send_channel = YM_CLOSE_PCT_DOWN
        elif index == 'GD':
            send_channel = GD_CLOSE_PCT_DOWN
    
        send_message_time = time.time()
        if len(readout_message_list) > 0:
            for pos, readout_message in enumerate(readout_message_list):
                display_message = display_message_list[pos]
                send_message(channel=send_channel, message=readout_message, tts=True)
                send_message(channel=send_channel, message=display_message, tts=False)
    
                save_ticker = save_db_params_list[pos][0]
                save_hit_scanner_datetime = save_db_params_list[pos][1]
                execute_in_transaction("""INSERT INTO PATTERN_ANALYSIS 
                                        (TICKER, HIT_SCANNER_DATETIME, SCAN_PATTERN, BAR_SIZE) 
                                        VALUES (?, ?, ?, ?)""",
                                        (save_ticker, save_hit_scanner_datetime, f'{index}_CLOSE_PCT_DIP', '1min'))
        print(f'{index} close pct dip send message time: {time.time() - send_message_time} seconds')

