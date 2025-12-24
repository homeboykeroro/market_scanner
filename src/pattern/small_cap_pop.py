import datetime
import time
import pandas as pd
import pytz

from discord.discord_client import SMALL_CAP_POP, send_message

from utils.datetime_util import convert_into_human_readable_time, convert_into_read_out_time
from utils.dataframe_util import get_ticker_to_occurrence_idx_list
from utils.logger import Logger

from database.sqlite_connector import execute_in_transaction

idx = pd.IndexSlice
logger = Logger()

MIN_GAP_UP_PCT = 5
MIN_CLOSE_PCT = 5
MIN_PREVIOUS_CLOSE_PCT = 15
MAX_POP_OCCURRENCE = 10
HIT_SCANNER_VALID_PERIOD_IN_MIN = 10

def analyse_small_cap_pop(minute_df, daily_df) -> None:
    analyse_start_time = time.time()
    
    close_pct_df = minute_df.loc[:, idx[:, 'Close Change%']].rename(columns={'Close Change%': 'Compare'})

    us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
    
    if datetime.time(4, 0, 0) <= us_current_datetime.time() <= datetime.time(9, 30, 0):
        previous_day_df = daily_df.iloc[[-1]] 
    if us_current_datetime.time() >= datetime.time(16, 0, 0):
        previous_day_df = daily_df.iloc[[-1]]
    if (datetime.time(0, 0, 0) <= us_current_datetime.time() < datetime.time(4, 0, 0)):
        previous_day_df = daily_df.iloc[[-1]]
    
    print(f'Analyse small cap pop previous day value: {previous_day_df.iloc[[0]].index[-1]}')
    
    previous_close_pct_df = (((minute_df.loc[:, idx[:, 'Close']].sub(previous_day_df.loc[:, idx[:, 'Close']].values))
                                                                .div(previous_day_df.loc[:, idx[:, 'Close']].values))
                                                                .mul(100)).rename(columns={'Close': 'Compare'})
    lower_body_df = minute_df.loc[:, idx[:, 'Candle Lower Body']].rename(columns={'Candle Lower Body': 'Compare'})
    
    previous_close_df = previous_day_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    previous_open_df = previous_day_df.loc[:, idx[:, 'Open']].rename(columns={'Open': 'Compare'})
    previos_close_above_previous_open_boolean_df = (previous_close_df > previous_open_df)
    
    previos_close_above_previous_open_upper_body_df = previous_close_df.where(previos_close_above_previous_open_boolean_df.values)
    previos_open_above_previous_close_upper_body_df = previous_open_df.where((~previos_close_above_previous_open_boolean_df).values)
    previos_upper_body_df = previos_close_above_previous_open_upper_body_df.fillna(previos_open_above_previous_close_upper_body_df)

    gap_up_pct_df = ((((lower_body_df.sub(previos_upper_body_df.iloc[[-1]].values))
                                     .div(previos_upper_body_df.iloc[[-1]].values)))
                                     .mul(100))
    candle_close_pct_boolean_df = (close_pct_df >= MIN_CLOSE_PCT)
    previous_close_pct_boolean_df = (previous_close_pct_df >= MIN_PREVIOUS_CLOSE_PCT)
    gap_up_pct_boolean_df = (gap_up_pct_df >= MIN_GAP_UP_PCT)
    pop_up_boolean_df = (candle_close_pct_boolean_df) & (previous_close_pct_boolean_df) & (gap_up_pct_boolean_df)
    
    ticker_to_occurrence_idx_list_dict = get_ticker_to_occurrence_idx_list(pop_up_boolean_df)
    print(f'small cap pop dict {ticker_to_occurrence_idx_list_dict}')
    logger.log_debug_msg(f'small cap pop dict {ticker_to_occurrence_idx_list_dict}')
    
    top_gainer_result_series = pop_up_boolean_df.any()   
    top_gainer_ticker_list = top_gainer_result_series.index[top_gainer_result_series].get_level_values(0).tolist()

    if len(top_gainer_ticker_list) > 0:
        readout_message_list = []
        display_message_list = []
        save_db_params_list = []
        
        for ticker in top_gainer_ticker_list:
            occurrence_idx_list = ticker_to_occurrence_idx_list_dict[ticker]

            for occurrence_idx in occurrence_idx_list:   
                if not occurrence_idx:
                    continue
                
                us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
                current_datetime_and_pop_up_time_diff = int(((us_current_datetime.replace(tzinfo=None) - datetime.datetime.strptime(occurrence_idx, '%Y-%m-%d %H:%M:%S')).total_seconds()) / 60)
                
                hit_scanner_date = datetime.datetime.strptime(occurrence_idx, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
                #debug
                #if True:
                if current_datetime_and_pop_up_time_diff <= HIT_SCANNER_VALID_PERIOD_IN_MIN:
                    pop_occurrence_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                      WHERE TICKER = ? 
                                                      AND DATE(HIT_SCANNER_DATETIME) = ? 
                                                      AND SCAN_PATTERN = ? 
                                                      AND BAR_SIZE = ?""",
                                                    (ticker, hit_scanner_date, 'SMALL_CAP_POP', '1min'))
                    pop_occurrence = dict(pop_occurrence_result[0])['ct']
                    
                    record_exist_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                      WHERE TICKER = ? 
                                                      AND HIT_SCANNER_DATETIME = ? 
                                                      AND SCAN_PATTERN = ? 
                                                      AND BAR_SIZE = ?""",
                                                    (ticker, occurrence_idx, 'SMALL_CAP_POP', '1min'))
                    record_count = dict(record_exist_result[0])['ct']
                    
                    notify = (pop_occurrence <= MAX_POP_OCCURRENCE) and (record_count == 0)
                    
                    if notify:
                        close = float(minute_df.loc[occurrence_idx, (ticker, 'Close')])
                        volume = int(minute_df.loc[occurrence_idx, (ticker, 'Volume')])
                        total_volume = int(minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
                        
                        yesterday_close = float(previous_day_df.loc[previous_day_df.index[-1], (ticker, 'Close')])
                        previous_close_pct = float(previous_close_pct_df.loc[occurrence_idx, (ticker, 'Compare')])
                        
                        hit_scanner_datetime_display = convert_into_human_readable_time(occurrence_idx)
                        read_out_pop_up_time = convert_into_read_out_time(occurrence_idx)
                        
                        readout_message = f'{" ".join(ticker)} is popping up {round(previous_close_pct, 2)}% at {read_out_pop_up_time}'
                        display_message = f'{ticker} is popping up {round(previous_close_pct, 2)}% at {hit_scanner_datetime_display}, close: {close}, previous close: {yesterday_close}, volume: {volume:,.2f}, total volume: {total_volume:,.2f}'
                        readout_message_list.append(readout_message)
                        display_message_list.append(display_message)
                        save_db_params_list.append((ticker, occurrence_idx))
                        print(f'${ticker} small cap pop, hit scanner datetime: {occurrence_idx}')
        
        print(f'Small cap pop analyse time: {time.time() - analyse_start_time} seconds')
        
        send_message_time = time.time()
        if len(readout_message_list) > 0:
            for pos, readout_message in enumerate(readout_message_list):
                display_message = display_message_list[pos]
                send_message(channel=SMALL_CAP_POP, message=readout_message, tts=True)
                send_message(channel=SMALL_CAP_POP, message=display_message, tts=False)
                
                save_ticker = save_db_params_list[pos][0]
                save_hit_scanner_datetime = save_db_params_list[pos][1]
                execute_in_transaction("""INSERT INTO PATTERN_ANALYSIS 
                                        (TICKER, HIT_SCANNER_DATETIME, SCAN_PATTERN, BAR_SIZE) 
                                        VALUES (?, ?, ?, ?)""",
                                        (save_ticker, save_hit_scanner_datetime, 'SMALL_CAP_POP', '1min'))
        print(f'Small cap pop send message time: {time.time() - send_message_time} seconds')