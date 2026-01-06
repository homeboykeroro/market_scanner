import datetime
from ibapi.scanner import ScannerSubscription
import pytz

def small_cap_pop_filter():
    scanner_filter = ScannerSubscription()
    
    # Get current datetime in HK time
    hk_datetime = datetime.datetime.now()
    
    # Convert Hong Kong time to US/Eastern time
    us_eastern_timezone = pytz.timezone('US/Eastern')
    hong_kong_timezone = pytz.timezone('Asia/Hong_Kong')
    hk_datetime = hong_kong_timezone.localize(hk_datetime)
    us_time = hk_datetime.astimezone(us_eastern_timezone)
    
    # Get current datetime in HK time
    hk_datetime = datetime.datetime.now()
    
    # Convert Hong Kong time to US/Eastern time
    us_eastern_timezone = pytz.timezone('US/Eastern')
    hong_kong_timezone = pytz.timezone('Asia/Hong_Kong')
    hk_datetime = hong_kong_timezone.localize(hk_datetime)
    us_time = hk_datetime.astimezone(us_eastern_timezone)
    
    #debug
    scanner_filter.scanCode = 'TOP_PERC_GAIN'
    scanner_filter.instrument = 'STK'
    scanner_filter.locationCode = 'STK.US.MAJOR'
    scanner_filter.numberOfRows = 10
    scanner_filter.abovePrice = 1
    scanner_filter.aboveVolume = 1000
    scanner_filter.marketCapAbove = 0
    scanner_filter.marketCapBelow = 500000000.0
    
    return scanner_filter