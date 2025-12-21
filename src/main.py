import time
import os
import traceback
from ib.ib_client import IBClient
from ib.screener_filter import small_cap_pop_filter
from discord.discord_client import MAIN_BOT, send_message
from exception.connection_exception import ConnectionException
from ibapi.contract import Contract

def main():
    ib_client = None
    
    try:
        ib_client = IBClient()
        ib_client.connect('127.0.0.1', 8888, 0)
        
        while True:
            #small_cap_pop_search_filter = small_cap_pop_filter()
            #ib_client.reqScannerSubscription(1, small_cap_pop_search_filter, [], [])
            
            # contract = Contract()
            # contract.symbol = "BTC"
            # contract.secType = "CRYPTO"
            # contract.currency = "USD"
            # contract.exchange = "PAXOS"
            
            # contract = Contract()
            # #contract.symbol = 'NQZ5'
            # contract.secType = "FUT"
            # contract.exchange = 'GLOBEX'
            # contract.currency = 'USD'
            # contract.localSymbol = 'NQ Dec1925'
            # #contract.lastTradeDateOrContractMonth = '202512'
            # contract.includeExpired = True
            
            # contract = Contract()
            # contract.symbol = "ETH"
            # contract.secType = "CRYPTO"
            # contract.currency = "USD"
            # contract.exchange = "PAXOS"
            
            nq_contract = Contract()
            nq_contract.symbol = "NQ"
            nq_contract.secType = "CONTFUT"
            nq_contract.exchange = "CME"
            #nq_contract.lastTradeDateOrContractMonth = '202603'
            #nq_contract.includeExpired=True
            
            es_contract = Contract()
            es_contract.symbol = "ES"
            es_contract.secType = "CONTFUT"
            es_contract.exchange = "CME"
            
            ym_contract = Contract()
            ym_contract.symbol = "YM"
            ym_contract.secType = "CONTFUT"
            ym_contract.exchange = "CME"
    
            ib_client.reqHistoricalData(10000, nq_contract, '', f'600 S', '1 min', 'TRADES', 0, 1, False, [])
            #ib_client.reqHistoricalData(20000, es_contract, '', f'2400 S', '1 min', 'TRADES', 0, 1, False, [])
            #ib_client.reqHistoricalData(30000, ym_contract, '', f'2400 S', '1 min', 'TRADES', 0, 1, False, [])
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