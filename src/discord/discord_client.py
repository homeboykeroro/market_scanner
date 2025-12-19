import requests

from utils.config_util import get_config
from utils.offline_tts import TextToSpeechEngine

tts = TextToSpeechEngine()

MAIN_BOT = 'CHATBOT'
SMALL_CAP_POP = 'SMALL CAP POP'

channel_to_url_dict = {
    MAIN_BOT: get_config('SMALL_CAP_POP', 'BOT_TOKEN'),
    SMALL_CAP_POP: get_config('SMALL_CAP_POP', 'BOT_TOKEN')
}

channel_to_bot_name_dict = {
    MAIN_BOT: 'chatbot',
    SMALL_CAP_POP: 'pop scanner'
}

def send_message(channel, message, tts=False):
    url = channel_to_url_dict[channel]
    
    if channel not in channel_to_url_dict:
        tts.speak(f'Cannot find channel type of {channel}')
        return
    
    headers = {"Content-Type": "application/json"}
    data = {"content": message, "username": channel_to_bot_name_dict[channel], "tts": tts}
    res = requests.post(url, headers=headers, json=data)
    if res.status_code not in (200, 204):
        tts.speak(f'Failed to send message to discord channe, channel type: {channel}')


