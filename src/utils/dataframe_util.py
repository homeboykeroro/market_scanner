import numpy as np
import pandas as pd

idx = pd.IndexSlice

def derive_idx_df(src_df, numeric_idx: bool = True):
    if numeric_idx:
        idx_np = src_df.reset_index(drop=True).reset_index().iloc[:, [0]].values
    else:
        idx_np = src_df.reset_index().iloc[:, [0]].values
    
    return pd.DataFrame(np.repeat(idx_np, len(src_df.columns), axis=1), 
                        columns=src_df.columns).rename(columns={src_df.columns.get_level_values(1).values[0]: 'Index'})

def get_ticker_to_occurrence_idx_list(occurrence_df, occurrence_limit: int = None) -> dict:
    result_dict = {}
    ticker_list = occurrence_df.columns.get_level_values(0).unique().tolist()
    idx_df = derive_idx_df(occurrence_df)

    occurrence_cumsum_df = occurrence_df.cumsum().where(occurrence_df.values) 
    
    if occurrence_limit:
        truncated_occurrence_cumsum_df = occurrence_cumsum_df.where((occurrence_cumsum_df <= occurrence_limit).values)
        normalised_idx_df = idx_df.where(truncated_occurrence_cumsum_df.notnull().values)
        normalised_cumsum_idx_np = np.sort(normalised_idx_df.values.T)[:, :occurrence_limit] 
    else:
        normalised_idx_df = idx_df.where(occurrence_cumsum_df.notnull().values)
        normalised_cumsum_idx_np = np.sort(normalised_idx_df.values.T)
    
    for index, ticker in enumerate(ticker_list):
        cumsum_idx_list = normalised_cumsum_idx_np[index] if not np.isnan(normalised_cumsum_idx_np[index]).all() else []
        datetime_idx_list = [occurrence_df.index[int(cumsum_idx)] if not np.isnan(cumsum_idx) else None for cumsum_idx in cumsum_idx_list]
        result_dict[ticker] = datetime_idx_list
        
    return result_dict

def append_customised_indicator(src_df: pd.DataFrame) -> pd.DataFrame:
    open_df = src_df.loc[:, idx[:, 'Open']].rename(columns={'Open': 'Compare'})
    high_df = src_df.loc[:, idx[:, 'High']].rename(columns={'High': 'Compare'})
    low_df = src_df.loc[:, idx[:, 'Low']].rename(columns={'Low': 'Compare'})
    close_df = src_df.loc[:, idx[:, 'Close']].rename(columns={'Close': 'Compare'})
    vol_df = src_df.loc[:, idx[:, 'Volume']]

    close_pct_df = close_df.pct_change().mul(100).rename(columns={'Compare': 'Close Change%'})
    
    flat_candle_df = (open_df == close_df).replace({True: 'Grey', False: np.nan})
    green_candle_df = (close_df > open_df).replace({True: 'Green', False: np.nan})
    red_candle_df = (close_df < open_df).replace({True: 'Red', False: np.nan})
    colour_df = ((flat_candle_df.fillna(green_candle_df))
                                .fillna(red_candle_df)
                                .rename(columns={'Compare': 'Candle Colour'}))

    vol_cumsum_df = vol_df.astype(float, errors = 'raise').cumsum().rename(columns={'Volume': 'Total Volume'})
    vol_20_ma_df = vol_df.rolling(window=20, min_periods=1).mean().rename(columns={'Volume': '20MA Volume'})
    vol_50_ma_df = vol_df.rolling(window=50, min_periods=1).mean().rename(columns={'Volume': '50MA Volume'})

    close_above_open_boolean_df = (close_df > open_df)
    close_above_open_upper_body_df = close_df.where(close_above_open_boolean_df.values)
    open_above_close_upper_body_df = open_df.where((~close_above_open_boolean_df).values)
    candle_upper_body_df = close_above_open_upper_body_df.fillna(open_above_close_upper_body_df)

    close_above_open_lower_body_df = open_df.where(close_above_open_boolean_df.values)
    open_above_close_lower_body_df = close_df.where((~close_above_open_boolean_df).values)
    candle_lower_body_df = close_above_open_lower_body_df.fillna(open_above_close_lower_body_df)

    shifted_upper_body_df = candle_upper_body_df.shift(periods=1)
    shifted_lower_body_df = candle_lower_body_df.shift(periods=1)
    gap_up_boolean_df = (candle_lower_body_df > shifted_upper_body_df)
    gap_down_boolean_df = (candle_upper_body_df < shifted_lower_body_df)
    no_gap_boolean_df = ((~gap_up_boolean_df) & (~gap_down_boolean_df))
    
    gap_up_pct_df = (((candle_lower_body_df.sub(shifted_upper_body_df.values))
                                           .div(shifted_upper_body_df.values))
                                           .mul(100)
                                           .where(gap_up_boolean_df.values)).rename(columns={'Compare': 'Gap Percent Change'})
    gap_down_pct_df = (((candle_upper_body_df.sub(shifted_lower_body_df.values))
                                             .div(candle_upper_body_df.values))
                                             .mul(100)
                                             .where(gap_down_boolean_df.values)).rename(columns={'Compare': 'Gap Percent Change'})
    gap_pct_df = ((gap_up_pct_df.fillna(gap_down_pct_df)
                                .where(~no_gap_boolean_df.values)))
    
    high_low_diff_df = high_df.sub(low_df.values)
    body_diff_df = candle_upper_body_df.sub(candle_lower_body_df.values)
    marubozu_ratio_df = (body_diff_df.div(high_low_diff_df.values)).mul(100).rename(columns={'Compare': 'Marubozu Ratio'})
    
    complete_df = pd.concat([src_df, 
                            close_pct_df,
                            gap_pct_df,
                            marubozu_ratio_df,
                            vol_20_ma_df,
                            vol_50_ma_df,
                            vol_cumsum_df,
                            colour_df,
                            candle_lower_body_df.rename(columns={'Compare': 'Candle Lower Body'}),
                            candle_upper_body_df.rename(columns={'Compare': 'Candle Upper Body'})], axis=1)

    return complete_df