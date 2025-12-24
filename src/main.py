import time
import os
import traceback
from ib.ib_client import IBClient
from ib.screener_filter import small_cap_pop_filter
from discord.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException

def main():
    ib_client = None
    
    try:
        ib_client = IBClient()
        
        while True:
            ib_client.connect('127.0.0.1', 8888, 0)
            small_cap_pop_search_filter = small_cap_pop_filter()
            ib_client.reqScannerSubscription(1, small_cap_pop_search_filter, [], [])
            ib_client.run()
    except Exception as e:
        if isinstance(e, ConnectionException):
            sleep_time = 180

            os.system('cls')
            print(f'TWS API Connection Lost, Cause: {e}')
            send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Connectivity Issue', tts=True)
        else:
            sleep_time = 10

            os.system('cls')
            print(traceback.format_exc())
            print(f'Fatal Error, Cause: {e}')
            send_message(channel=MAIN_BOT, message='Re-establishing Connection Due to Fatal Error', tts=True)
        
        if sleep_time:
            time.sleep(sleep_time)

        main()

if __name__ == '__main__':
    main()