import pandas as pd
import pytz
from datetime import datetime

from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    Holiday,
    GoodFriday,
    USFederalHolidayCalendar,
)
from pandas.tseries.offsets import CustomBusinessDay

class USStockMarketCalendar(AbstractHolidayCalendar):
    """
    NYSE/NASDAQ trading day calendar:
    - All US federal holidays (with observed rules)
    - Plus Good Friday (markets closed)
    - Excludes non-market-closing federal holidays like Columbus Day (harmless to include)
    """
    rules = USFederalHolidayCalendar.rules + [GoodFriday]

# Create the calendar and business day offset
US_STOCK_CALENDAR = USStockMarketCalendar()
US_BUSINESS_DAY = CustomBusinessDay(calendar=US_STOCK_CALENDAR)
US_EASTERN_TIMEZONE = pytz.timezone('US/Eastern')

def convert_into_human_readable_time(pop_up_datetime):
    pop_up_hour = pd.to_datetime(pop_up_datetime).hour
    pop_up_minute = pd.to_datetime(pop_up_datetime).minute
    display_hour = ('0' + str(pop_up_hour)) if pop_up_hour < 10 else pop_up_hour
    display_minute = ('0' + str(pop_up_minute)) if pop_up_minute < 10 else pop_up_minute
    return f'{display_hour}:{display_minute}'

def convert_into_read_out_time(pop_up_datetime):
    pop_up_hour = pd.to_datetime(pop_up_datetime).hour
    pop_up_minute = pd.to_datetime(pop_up_datetime).minute
    
    read_out_time = f'{pop_up_hour} {pop_up_minute}' if (pop_up_minute > 0) else f'{pop_up_hour} o clock' 
    return read_out_time

def convert_to_eastern(dt_string):
    # Split off the timezone name (last part after space)
    naive_str, tz_name = dt_string.rsplit(' ', 1)
    
    # Parse the naive datetime
    naive_dt = datetime.strptime(naive_str, '%Y%m%d %H:%M:%S')
    
    # Get the source timezone (use canonical names for pytz)
    if tz_name == 'US/Central':
        source_tz = pytz.timezone('America/Chicago')
    elif tz_name == 'US/Eastern':
        source_tz = pytz.timezone('America/New_York')
    else:
        raise ValueError(f"Unsupported timezone: {tz_name}")
    
    # Localize the naive datetime to the source timezone
    localized_dt = source_tz.localize(naive_dt)
    
    # Convert to US/Eastern
    eastern_tz = pytz.timezone('America/New_York')
    converted_dt = localized_dt.astimezone(eastern_tz)
    
    # Format back to your desired string format
    new_string = converted_dt.strftime('%Y-%m-%d %H:%M:%S') + ' US/Eastern'
    
    return new_string

def get_us_business_day(offset_day: int, us_date: datetime = None) -> datetime:
    """
    Returns a US/Eastern timezone-aware datetime offset by the given number of
    NYSE trading (business) days.
    
    offset_day > 0: future trading days
    offset_day < 0: previous trading days
    offset_day = 0: same day if it's a trading day, else next trading day (pandas default)
    
    If us_date is None, uses current US Eastern time.
    """
    if us_date is None:
        base_dt = datetime.now(US_EASTERN_TIMEZONE)
    else:
        # Ensure it's timezone-aware in US/Eastern
        if us_date.tzinfo is None:
            base_dt = US_EASTERN_TIMEZONE.localize(us_date)
        else:
            base_dt = us_date.astimezone(US_EASTERN_TIMEZONE)
    
    # Apply the offset using accurate stock market calendar
    result_dt = base_dt + (offset_day * US_BUSINESS_DAY)
    
    return result_dt