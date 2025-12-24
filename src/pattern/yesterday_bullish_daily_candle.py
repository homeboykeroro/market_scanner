import datetime
import time
import pandas as pd
import pytz

from discord.discord_client import YESTERDAY_BULLISH_DAILY_CANDLE, send_message

from utils.datetime_util import convert_into_human_readable_time, convert_into_read_out_time
from utils.dataframe_util import get_ticker_to_occurrence_idx_list
from utils.logger import Logger

from database.sqlite_connector import execute_in_transaction

idx = pd.IndexSlice
logger = Logger()

MIN_YESTERDAY_CLOSE_CHANGE_PCT = 30

def analyse_yesterday_bullish_daily_candle(minute_df, daily_df) -> None:
    analyse_start_time = time.time()
    us_current_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
    
    # if us_current_datetime.time() <= datetime.time(16, 0, 0):
    #     return
    
    select_afterhour_datetime = us_current_datetime.replace(day=us_current_datetime.day - 1, hour=16, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S') if (datetime.time(0, 0, 0) <= us_current_datetime.time() < datetime.time(16, 0, 0)) else us_current_datetime.replace(hour=4, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    afterhour_minute_df = minute_df.loc[select_afterhour_datetime:, :]
    print(f'Yesterday bullish daily candle select afterhour datetime: {select_afterhour_datetime}')

    close_df = afterhour_minute_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    candle_colour_df = minute_df.loc[:, idx[:, 'Candle Colour']].rename(columns={'Candle Colour': 'Compare'})

    if datetime.time(4, 0, 0) <= us_current_datetime.time() <= datetime.time(9, 30, 0):
        previous_day_df = daily_df.iloc[[0]] 
    if us_current_datetime.time() >= datetime.time(16, 0, 0):
        previous_day_df = daily_df.iloc[[-1]]
    if (datetime.time(0, 0, 0) <= us_current_datetime.time() < datetime.time(16, 0, 0)):
        previous_day_df = daily_df.iloc[[-1]]
        
    print(f'Analyse yesterday bullish daily candle previous day value: {previous_day_df.iloc[[0]].index[-1]}')
    
    previous_close_df = previous_day_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    
    previous_close_pct_df = (((close_df.sub(previous_close_df.values))
                                       .div(previous_close_df.values))
                                       .mul(100))
    
    bullish_candle_boolean_df = (candle_colour_df == 'Green') & (previous_close_pct_df >= MIN_YESTERDAY_CLOSE_CHANGE_PCT)
    
    ticker_to_occurrence_idx_list_dict = get_ticker_to_occurrence_idx_list(bullish_candle_boolean_df)
    
    bullish_daily_candle_result_series = bullish_candle_boolean_df.any()   
    bullish_daily_candle_ticker_list = bullish_daily_candle_result_series.index[bullish_daily_candle_result_series].get_level_values(0).tolist()
    
    if len(bullish_daily_candle_ticker_list) > 0: 
        for ticker in bullish_daily_candle_ticker_list:
            occurrence_idx_list = ticker_to_occurrence_idx_list_dict[ticker]

            for occurrence_idx in occurrence_idx_list:   
                if not occurrence_idx:
                    continue
                
                hit_scanner_date = datetime.datetime.strptime(occurrence_idx, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
                #debug
                #if True:
                occurrence_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM PATTERN_ANALYSIS 
                                                  WHERE TICKER = ? 
                                                  AND DATE(HIT_SCANNER_DATETIME) = ? 
                                                  AND SCAN_PATTERN = ? 
                                                  AND BAR_SIZE = ?""",
                                                (ticker, hit_scanner_date, 'YESTERDAY_BULLISH_DAILY_CANDLE', '1day'))
                occurrence = dict(occurrence_result[0])['ct']
                
                notify = (occurrence == 0)
                
                if notify:
                    close = float(minute_df.loc[occurrence_idx, (ticker, 'Close')])
                    total_volume = int(minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
                        
                    yesterday_close = float(previous_day_df.loc[previous_day_df.index[-1], (ticker, 'Close')])
                    previous_close_pct = float(previous_close_pct_df.loc[occurrence_idx, (ticker, 'Compare')])
                        
                    hit_scanner_datetime_display = convert_into_human_readable_time(occurrence_idx)
                    read_out_pop_up_time = convert_into_read_out_time(occurrence_idx)
                        
                    readout_message = f'{" ".join(ticker)} yesterday bullish daily candle, up {round(previous_close_pct, 2)}% at {read_out_pop_up_time}'
                    display_message = f'{ticker} yesterday bullish daily candle, up {round(previous_close_pct, 2)}% at {hit_scanner_datetime_display}, close: {close}, previous close: {yesterday_close}, total volume: {total_volume:,.2f}'
                    
                    send_message(channel=YESTERDAY_BULLISH_DAILY_CANDLE, message=readout_message, tts=True)
                    send_message(channel=YESTERDAY_BULLISH_DAILY_CANDLE, message=display_message, tts=False)

                    execute_in_transaction("""INSERT INTO PATTERN_ANALYSIS 
                                            (TICKER, HIT_SCANNER_DATETIME, SCAN_PATTERN, BAR_SIZE) 
                                            VALUES (?, ?, ?, ?)""",
                                            (ticker, occurrence_idx, 'YESTERDAY_BULLISH_DAILY_CANDLE', '1day'))
                    
                    print(f'${ticker} yesterday bullish daily candle, hit scanner datetime: {occurrence_idx}')
        
    print(f'Yesterday bullish daily candle analyse time: {time.time() - analyse_start_time} seconds')
        