import datetime
import time
import pandas as pd
import pytz

from notification.discord_client import YESTERDAY_BULLISH_DAILY_CANDLE, send_message

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
    
    if (not (us_current_datetime.time() > datetime.time(16, 0, 0))):
        print('yesterday bullish daily candle analysis is idle...')
        return

    top_gainer_ticker_list = list(set(minute_df.columns.get_level_values(0).to_list()))
    latest_minute_date = minute_df.iloc[[-1]].index.tolist()[0].strftime('%Y-%m-%d')
    print(f'yesterday bullish daily candle latest_minute_date: {latest_minute_date}')
    filtered_ticker_list = []
    
    for rank, top_gainer_ticker in enumerate(top_gainer_ticker_list):
        record_count_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM TOP_GAINER_HISTORY
                                                        WHERE TICKER = ?
                                                        AND DATE(SCAN_DATE) = ?
                                                        ORDER BY SCAN_DATE DESC
                                                    """,
                                                    (top_gainer_ticker, latest_minute_date))
        record_count = dict(record_count_result[0])['ct']
        if record_count > 0:
            filtered_ticker_list.append(top_gainer_ticker)
    
    print(f'filtered previous top gainer ticker list: {filtered_ticker_list}')
    
    if len(filtered_ticker_list) < 1:
        print(f'no top gainer ticker found in yesterday bullish daily candle...')
        return
    
    after_hour_start_datetime = latest_minute_date + ' ' + '16:00:00'
    afterhour_minute_df = minute_df.loc[after_hour_start_datetime:, idx[filtered_ticker_list], :]
    print(f'Yesterday bullish daily candle select afterhour datetime: {after_hour_start_datetime}')

    close_df = afterhour_minute_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    candle_colour_df = afterhour_minute_df.loc[:, idx[:, 'Candle Colour']].rename(columns={'Candle Colour': 'Compare'})
    previous_day_df = daily_df.iloc[[-1]]
        
    print(f'Analyse yesterday bullish daily candle previous day value: {previous_day_df.iloc[[0]].index[-1]}')
    
    previous_close_df = previous_day_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    
    sub_df = close_df.sub(previous_close_df.values)
    div_df = sub_df.div(previous_close_df.values)
    previous_close_pct_df = div_df.mul(100)
    
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
                    close = float(afterhour_minute_df.loc[occurrence_idx, (ticker, 'Close')])
                    total_volume = int(afterhour_minute_df.loc[occurrence_idx, (ticker, 'Total Volume')])
                        
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
        