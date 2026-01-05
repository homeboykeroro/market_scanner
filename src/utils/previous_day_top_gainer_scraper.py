import datetime
import pytz
import re
import time
import traceback
from bs4 import BeautifulSoup
import requests

from database.sqlite_connector import execute_in_transaction
from notification.discord_client import MAIN_BOT, send_message

#from utils.logger import Logger

FINVIZ_LINK = 'https://finviz.com/screener.ashx'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0'}
TOP_GAINER_PAYLOAD = {'s': 'ta_topgainers'}

session = requests.Session()
#logger = Logger()

def scrap_previous_day_top_gainer(): 
    start_time = time.time() 
    scrape_datetime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))

    today_top_gainer_count_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM TOP_GAINER_HISTORY 
                                                              WHERE DATE(SCAN_DATE) = ? 
                                                            """,
                                                               (scrape_datetime.strftime('%Y-%m-%d'),))
    today_top_gainer_count = dict(today_top_gainer_count_result[0])['ct']
    
    if today_top_gainer_count > 0:
        print(f'{scrape_datetime.strftime('%Y-%m-%d')} top gainer history already added before')
        return
    
    try:
        scrap_start_time = time.time()
        response = session.get(FINVIZ_LINK, params=TOP_GAINER_PAYLOAD, headers=HEADERS)
        print(f'Scrap {FINVIZ_LINK} response time: {time.time() - scrap_start_time} seconds')
        # Raises a HTTPError if the response status is 4xx, 5xx
        response.raise_for_status() 
    except Exception as e:
        print(f'An error occurred while scarping data: {e}')
    else:
        top_gainer_list = []
        contents = response.text
        soup = BeautifulSoup(contents, 'lxml')
        row_list = soup.select('table.screener_table tr.styled-row')

        try:
            for row in row_list:
                column_list = row.find_all('td')
                ticker = column_list[1].text
                
                if not re.match('^[a-zA-Z]{1,4}$', ticker):
                    print(f'Exclude {ticker} from previous day top gainer list')
                    continue
                
                company = column_list[2].text
                sector = column_list[3].text
                industry = column_list[4].text
                country = column_list[5].text
                market_cap_str = column_list[6].text
                close_price = float(column_list[8].text.replace(',', ''))
                change_pct = float(column_list[9].text.replace('%', ''))
                volume = int(column_list[10].text.replace(',', ''))

                market_cap = 0
                if market_cap_str:
                    multiplier = 1

                    if market_cap_str.endswith('K'):
                        multiplier = 1e4
                    if market_cap_str.endswith('M'):
                        multiplier = 1e6
                    elif market_cap_str.endswith('B'):
                        multiplier = 1e9

                    market_cap_str = market_cap_str[:-1]
                    num = float(market_cap_str.replace(',', '')) if market_cap_str else 0
                    market_cap = int(num * multiplier)
                
                hit_scanner_date = scrape_datetime.strftime('%Y-%m-%d')
                top_gainer_count_result = execute_in_transaction("""SELECT COUNT(*) AS ct FROM TOP_GAINER_HISTORY 
                                                                    WHERE TICKER = ? 
                                                                    AND DATE(SCAN_DATE) = ? 
                                                                """,
                                                               (ticker, hit_scanner_date))
                top_gainer_count = dict(top_gainer_count_result[0])['ct']
                
                if top_gainer_count == 0:
                    top_gainer_list.append([ticker, 
                                            company, sector, industry, 
                                            scrape_datetime, 
                                            close_price, 
                                            volume, change_pct, 
                                            market_cap, country])
            
            if top_gainer_list:
                for rank, top_gainer_record in enumerate(top_gainer_list):
                    insert_ticker = top_gainer_record[0]
                    insert_company = top_gainer_record[1]
                    insert_sector = top_gainer_record[2]
                    insert_industry = top_gainer_record[3]
                    insert_scrape_datetime = top_gainer_record[4]
                    insert_close_price = top_gainer_record[5]
                    insert_volume = top_gainer_record[6]
                    insert_change_pct = top_gainer_record[7]
                    insert_market_cap = top_gainer_record[8]
                    insert_country = top_gainer_record[9]
                    execute_in_transaction("""INSERT INTO TOP_GAINER_HISTORY 
                                              (TICKER, COMPANY, SECTOR, INDUSTRY, SCAN_DATE, PRICE, VOLUME, PERCENTAGE, MARKET_CAP, COUNTRY)
                                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                           (insert_ticker, 
                                            insert_company, insert_sector, insert_industry, 
                                            insert_scrape_datetime, 
                                            insert_close_price, 
                                            insert_volume, insert_change_pct, 
                                            insert_market_cap, insert_country))

                send_message(channel=MAIN_BOT, message='Previous day top gainer history retrieval succeed', tts=True)
                send_message(channel=MAIN_BOT, message=f'Yesterday top gainer history: {[f"{top_gainer[0]} ({top_gainer[1]}): {top_gainer[7]}%" for top_gainer in top_gainer_list]}', tts=False)
                print('Previous day top gainer history retrieval succeed')
                print(f'Yesterday top gainer history: {[f"{top_gainer[0]} ({top_gainer[1]}): {top_gainer[7]}%" for top_gainer in top_gainer_list]}')
            else:
                send_message(channel=MAIN_BOT, message='No previous day top gainer history is added', tts=True)
                print('No previous day top gainer history is added')
                
            print(f'Previous day top gainers scraping completed, finished in {time.time() - start_time} seconds')
        except Exception as e:
            send_message(channel=MAIN_BOT, message='Previous day top gainer history retrieval failed', tts=True)
            print(traceback.format_exc())
            print(f'Previous day top gainer history retrieval failed, Error: {e}')
            raise e