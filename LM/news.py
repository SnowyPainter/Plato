import requests
from bs4 import BeautifulSoup
import re

def preprocess_text(texts):
    processed_texts = []
    for text in texts:
        text = re.sub(r'\s+', ' ', text)  # 여러 공백을 하나의 공백으로
        text = re.sub(r'[^가-힣\s]', '', text)  # 한글과 공백을 제외한 문자 제거
        processed_texts.append(text.strip())  # 양쪽 공백 제거
    return processed_texts

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