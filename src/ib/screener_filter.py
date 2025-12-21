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

    if ((datetime.time(4, 0, 0) <= us_time.time() < datetime.time(9, 30, 0))
            or (datetime.time(9, 30, 0) <= us_time.time() < datetime.time(16, 0, 0))):
        #logger.log_debug_msg('Pre-market trading hours')
        scan_code = 'TOP_PERC_GAIN'
    elif datetime.time(16, 0, 0) <= us_time.time() < datetime.time(20, 0, 0):
        #logger.log_debug_msg('After hours trading hours')
        scan_code = 'TOP_AFTER_HOURS_PERC_GAIN'
    
    #debug
    #scanner_filter.scanCode = 'TOP_PERC_GAIN'
    scanner_filter.scanCode = scan_code
    scanner_filter.instrument = 'STK'
    scanner_filter.locationCode = 'STK.US.MAJOR'
    scanner_filter.numberOfRows = 10
    scanner_filter.abovePrice = 1
    scanner_filter.aboveVolume = 1000
    scanner_filter.marketCapAbove = 0
    scanner_filter.marketCapBelow = 500000000.0
    
    return scanner_filter