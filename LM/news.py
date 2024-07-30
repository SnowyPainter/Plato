import requests
from bs4 import BeautifulSoup

def get_page(symbol, n):
    url = f"https://finance.naver.com/item/news_news.naver?code={symbol}&page={n}&clusterId="
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    data = []
    for row in soup.select('tbody tr'):
        title = row.select_one('a').get_text(strip=True)
        date = row.select_one('td.date').get_text(strip=True)
        data.append({'title': title, 'date': date})
    return data