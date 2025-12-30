import pandas as pd
import pytz

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

from datetime import datetime
import pytz

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
