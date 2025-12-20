import time
import pandas as pd
from pandas.core.frame import DataFrame

from utils.dataframe_util import derive_idx_df
from utils.logger import Logger

idx = pd.IndexSlice
logger = Logger()

MIN_MARUBOZU_RATIO = 65
MIN_CLOSE_PCT = 4.2
MIN_VOLUME = 3000
        
def analyse_small_cap_ramp_up(src_df):
    start_time = time.time()
    
    close_df = src_df.loc[:, idx[:, 'Close']]
    close_pct_df = src_df.loc[:, idx[:, 'Close Change%']].rename(columns={'Close Change%': 'Compare'})
    previous_close_df = src_df.loc[:, idx[:, 'Previous Close']]
    previous_close_pct_df = src_df.loc[:, idx[:, 'Previous Close']]
    candle_colour_df = src_df.loc[:, idx[:, 'Candle Colour']].rename(columns={'Candle Colour': 'Compare'})
    marubozu_ratio_df = src_df.loc[:, idx[:, 'Marubozu Ratio']].rename(columns={'Marubozu Ratio': 'Compare'})
    volume_df = src_df.loc[:, idx[:, 'Volume']].rename(columns={'Volume': 'Compare'})
    total_volume_df = src_df.loc[:, idx[:, 'Total Volume']]
    vol_20_ma_df = src_df.loc[:, idx[:, '20MA Volume']].rename(columns={'20MA Volume': 'Compare'})
    vol_50_ma_df = src_df.loc[:, idx[:, '50MA Volume']].rename(columns={'50MA Volume': 'Compare'})
    
    green_candle_df = (candle_colour_df == 'GREEN')
    marubozu_boolean_df = (marubozu_ratio_df >= MIN_MARUBOZU_RATIO)
    candle_close_pct_boolean_df = (close_pct_df >= MIN_CLOSE_PCT)
    ramp_up_boolean_df = (green_candle_df) & (marubozu_boolean_df) & (candle_close_pct_boolean_df)
    above_vol_20_ma_boolean_df = (volume_df >= vol_20_ma_df) & (vol_20_ma_df >= MIN_VOLUME) & (ramp_up_boolean_df)
    above_vol_50_ma_boolean_df = (volume_df >= vol_50_ma_df) & (vol_50_ma_df >= MIN_VOLUME) & (ramp_up_boolean_df)
    
    above_vol_20_ma_result_boolean_df = above_vol_20_ma_boolean_df.iloc[-NOTIFY_PERIOD:]
    above_vol_20_ma_result_series = above_vol_20_ma_result_boolean_df.any()
    above_vol_20_ma_ticker_list = above_vol_20_ma_result_series.index[above_vol_20_ma_result_series].get_level_values(0).tolist()
    
    above_vol_50_ma_result_boolean_df = above_vol_50_ma_boolean_df.iloc[-NOTIFY_PERIOD:]
    above_vol_50_ma_result_series = above_vol_50_ma_result_boolean_df.any()
    above_vol_50_ma_ticker_list = above_vol_50_ma_result_series.index[above_vol_50_ma_result_series].get_level_values(0).tolist()
    
    above_vol_20_ma_ticker_list = [ticker for ticker in above_vol_20_ma_ticker_list if ticker not in above_vol_50_ma_ticker_list]
    
    if len(above_vol_20_ma_ticker_list) > 0 or len(above_vol_50_ma_ticker_list) > 0:
        result_ticker_list = [above_vol_20_ma_ticker_list, above_vol_50_ma_ticker_list]
        
        for list_idx, ticker_list in enumerate(result_ticker_list):
            if len(ticker_list) > 0:
                ma_val = '20' if (list_idx == 0) else '50'
                above_ma_df = above_vol_20_ma_boolean_df if (list_idx == 0) else above_vol_50_ma_boolean_df
                ma_vol_df = vol_20_ma_df if (list_idx == 0) else vol_50_ma_df
                
                datetime_idx_df = derive_idx_df(above_ma_df, numeric_idx=False)
                ramp_up_datetime_idx_df = datetime_idx_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_close_df = close_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_close_pct_df = close_pct_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_previous_close_df = previous_close_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_previous_close_pct_df = previous_close_pct_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_volume_df = volume_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_total_volume_df = total_volume_df.where(above_ma_df.values).ffill().iloc[[-1]]
                ramp_up_ma_vol_df = ma_vol_df.where(above_ma_df.values).ffill().iloc[[-1]]
                
                for ticker in ticker_list:
                    display_close = ramp_up_close_df.loc[:, ticker].iat[0, 0]
                    volume = ramp_up_volume_df.loc[:, ticker].iat[0, 0]
                    display_volume = "{:,}".format(volume)
                    display_total_volume = "{:,}".format(ramp_up_total_volume_df.loc[:, ticker].iat[0, 0])
                    display_close_pct = round(ramp_up_close_pct_df.loc[:, ticker].iat[0, 0], 2)
                    display_ma_vol = ramp_up_ma_vol_df.loc[:, ticker].iat[0, 0]
                    display_previous_close = ramp_up_previous_close_df.loc[:, ticker].iat[0, 0]
                    display_previous_close_pct = round(ramp_up_previous_close_pct_df.loc[:, ticker].iat[0, 0], 2)
                
                    ramp_up_datetime = ramp_up_datetime_idx_df.loc[:, ticker].iat[0, 0]
                    ramp_up_hour = pd.to_datetime(ramp_up_datetime).hour
                    ramp_up_minute = pd.to_datetime(ramp_up_datetime).minute
                    display_hour = ('0' + str(ramp_up_hour)) if ramp_up_hour < 10 else ramp_up_hour
                    display_minute = ('0' + str(ramp_up_minute)) if ramp_up_minute < 10 else ramp_up_minute
                    display_time_str = f'{display_hour}:{display_minute}'
                    read_time_str = f'{ramp_up_hour} {ramp_up_minute}' if (ramp_up_minute > 0) else f'{ramp_up_hour} o clock' 
                    read_ticker_str = " ".join(ticker)
                
                    logger.log_debug_msg(f'{ticker} ramp up {display_close_pct}% above {ma_val}MA volume at {display_time_str}, {ma_val}MA volume: {display_ma_vol}, Volume: {display_volume}, Total volume: {display_total_volume}, Volume ratio: {round((float(volume)/ display_ma_vol), 1)}, Close: ${display_close}, Previous close: {display_previous_close}, Previous close change: {display_previous_close_pct}%', with_std_out = True)
                    logger.log_debug_msg(f'{read_ticker_str} ramp up {display_close_pct} percent above {ma_val} M A volume at {read_time_str}, Ratio: {round((float(volume)/ display_ma_vol), 1)}', with_speech = True, with_log_file = False)
                    
    logger.log_debug_msg(f'Unusual volume analysis time: {time.time() - start_time} seconds')