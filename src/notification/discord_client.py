import time
import requests

from utils.logger import Logger
from utils.config_util import get_config
from utils.offline_tts import TextToSpeechEngine

#logger = Logger()
text_to_speech_engine = TextToSpeechEngine()

MAIN_BOT = 'CHATBOT'
SMALL_CAP_POP = 'SMALL CAP POP'
SMALL_CAP_RAMP_UP = 'SMALL CAP RAMP UP'
YESTERDAY_BULLISH_DAILY_CANDLE = 'YESTERDAY BULLISH DAILY CANDLE'
NQ_RAMP_UP = 'NQ RAMP UP'
ES_RAMP_UP = 'ES RAMP UP'
YM_RAMP_UP = 'YM RAMP UP'
GD_RAMP_UP = 'GD RAMP UP'
NQ_CLOSE_PCT_UP = 'NQ CLOSE PCT UP'
ES_CLOSE_PCT_UP = 'ES CLOSE PCT UP'
YM_CLOSE_PCT_UP = 'YM CLOSE PCT UP'
GD_CLOSE_PCT_UP = 'GD CLOSE PCT UP'
NQ_DIP = 'NQ DIP'
ES_DIP = 'ES DIP'
YM_DIP = 'YM DIP'
GD_DIP = 'GD DIP'
NQ_CLOSE_PCT_DOWN = 'NQ CLOSE PCT DOWN'
ES_CLOSE_PCT_DOWN = 'ES CLOSE PCT DOWN'
YM_CLOSE_PCT_DOWN = 'YM CLOSE PCT DOWN'
GD_CLOSE_PCT_DOWN = 'YM CLOSE PCT DOWN'

channel_to_url_dict = {
    MAIN_BOT: get_config('MAIN', 'BOT_TOKEN'),
    SMALL_CAP_POP: get_config('SMALL_CAP_POP', 'BOT_TOKEN'),
    SMALL_CAP_RAMP_UP: get_config('SMALL_CAP_RAMP_UP', 'BOT_TOKEN'),
    YESTERDAY_BULLISH_DAILY_CANDLE: get_config('YESTERDAY_BULLISH_DAILY_CANDLE', 'BOT_TOKEN'),
    NQ_RAMP_UP: get_config('NQ_RAMP_UP', 'BOT_TOKEN'),
    NQ_CLOSE_PCT_UP: get_config('NQ_CLOSE_PCT_UP', 'BOT_TOKEN'),
    NQ_DIP: get_config('NQ_DIP', 'BOT_TOKEN'),
    NQ_CLOSE_PCT_DOWN: get_config('NQ_CLOSE_PCT_DOWN', 'BOT_TOKEN'),
    ES_RAMP_UP: get_config('ES_RAMP_UP', 'BOT_TOKEN'),
    ES_CLOSE_PCT_UP: get_config('ES_CLOSE_PCT_UP', 'BOT_TOKEN'),
    ES_DIP: get_config('ES_DIP', 'BOT_TOKEN'),
    ES_CLOSE_PCT_DOWN: get_config('ES_CLOSE_PCT_DOWN', 'BOT_TOKEN'),
    YM_RAMP_UP: get_config('YM_RAMP_UP', 'BOT_TOKEN'),
    YM_CLOSE_PCT_UP: get_config('YM_CLOSE_PCT_UP', 'BOT_TOKEN'),
    YM_DIP: get_config('YM_DIP', 'BOT_TOKEN'),
    YM_CLOSE_PCT_DOWN: get_config('YM_CLOSE_PCT_DOWN', 'BOT_TOKEN'),
    GD_RAMP_UP: get_config('GD_RAMP_UP', 'BOT_TOKEN'),
    GD_CLOSE_PCT_UP: get_config('GD_CLOSE_PCT_UP', 'BOT_TOKEN'),
    GD_DIP: get_config('GD_DIP', 'BOT_TOKEN'),
    GD_CLOSE_PCT_DOWN: get_config('GD_CLOSE_PCT_DOWN', 'BOT_TOKEN')
}

channel_to_bot_name_dict = {
    MAIN_BOT: 'chatbot',
    SMALL_CAP_POP: 'pop scanner',
    SMALL_CAP_RAMP_UP: 'ramp up scanner',
    YESTERDAY_BULLISH_DAILY_CANDLE: 'pop scanner',
    NQ_RAMP_UP: 'ramp up scanner',
    NQ_CLOSE_PCT_UP: 'pop scanner',
    NQ_DIP: 'dip scanner',
    NQ_CLOSE_PCT_DOWN: 'dip scanner',
    ES_RAMP_UP: 'ramp up scanner',
    ES_CLOSE_PCT_UP: 'pop scanner',
    ES_DIP: 'dip scanner',
    ES_CLOSE_PCT_DOWN: 'dip scanner',
    YM_RAMP_UP: 'ramp up scanner',
    YM_CLOSE_PCT_UP: 'pop scanner',
    YM_DIP: 'dip scanner',
    YM_CLOSE_PCT_DOWN: 'dip scanner',
    GD_RAMP_UP: 'ramp up scanner',
    GD_CLOSE_PCT_UP: 'pop scanner',
    GD_DIP: 'dip scanner',
    GD_CLOSE_PCT_DOWN: 'dip scanner'
}

def send_message(channel, message, tts=False):
    url = channel_to_url_dict[channel]
    
    if channel not in channel_to_url_dict:
        print(f'Cannot find channel type of {channel}')
        #logger.log_debug_msg(f'Cannot find channel type of {channel}')
        text_to_speech_engine.speak(f'Cannot find channel type of {channel}')
        return
    
    headers = {"Content-Type": "application/json"}
    data = {"content": message, "username": channel_to_bot_name_dict[channel], "tts": tts}
    res = requests.post(url, headers=headers, json=data)
    
    if res.status_code in (200, 204):
        time.sleep(0.2)
        return True
    elif res.status_code == 429:
        # Rare now, but safe to handle
        retry_after = res.headers.get("Retry-After", 2)
        print(f'Rate limited on {channel}, waiting {retry_after}s...')
        #logger.log_debug_msg(f'Rate limited on {channel}, waiting {retry_after}s...')
        text_to_speech_engine.speak(f'Rate limited on {channel}, waiting {retry_after}s...')
        time.sleep(float(retry_after) + 1)
        # Optional: retry once
        res = requests.post(url, headers=headers, json=data)
        if res.status_code in (200, 204):
            time.sleep(0.2)
            return True
    else:
        print(f'Failed to send message to discord channe, channel type: {channel}, response code: {res.status_code}')
        #logger.log_debug_msg(f'Failed to send message to discord channe, channel type: {channel}, response code: {res.status_code}')
        text_to_speech_engine.speak(f'Failed to send message to discord channe, channel type: {channel}, response code: {res.status_code}')


