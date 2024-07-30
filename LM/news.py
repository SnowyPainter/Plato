import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import pandas as pd
import numpy as np
import re
from tqdm import tqdm
import urllib.request
import seaborn as sns
import matplotlib.pyplot as plt
import tensorflow_addons as tfa
import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from transformers import BertTokenizer, TFBertForSequenceClassification
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, \
                            roc_auc_score, confusion_matrix, classification_report, \
                            matthews_corrcoef, cohen_kappa_score, log_loss

class NewsReader:
    def _get_BertTokenizer(self):
        tokenizer = BertTokenizer.from_pretrained(self.MODEL_NAME)
        return tokenizer
    
    def _convert_data(self, X_data, y_data):
        tokenizer = self._get_BertTokenizer()
        tokens, masks, segments, targets = [], [], [], []
        
        for X, y in tqdm(zip(X_data, y_data)):
            token = tokenizer.encode(X, truncation = True, padding = 'max_length', max_length = self.MAX_SEQ_LEN)
            num_zeros = token.count(0)
            mask = [1] * (self.MAX_SEQ_LEN - num_zeros) + [0] * num_zeros
            segment = [0]*self.MAX_SEQ_LEN

            tokens.append(token)
            masks.append(mask)
            segments.append(segment)
            targets.append(y)
        tokens = np.array(tokens)
        masks = np.array(masks)
        segments = np.array(segments)
        targets = np.array(targets)

        return [tokens, masks, segments], targets
    
    def _get_dataset(self):
        urllib.request.urlretrieve(self.DATASET_URL, filename = self.DATASET_NAME)
        dataset = pd.read_csv(self.DATASET_NAME)
        del dataset['sentence']
        dataset['labels'] = dataset['labels'].replace(['neutral', 'positive', 'negative'],[0, 1, 2])
        dataset.drop_duplicates(subset = ['kor_sentence'], inplace = True)
        dataset.to_csv(self.DATASET_PREP_NAME) # 구글 드라이브 내 data 폴더에 저장
        
        X_data = dataset['kor_sentence']
        y_data = dataset['labels']
        X_train, X_test, y_train, y_test = train_test_split(X_data, y_data,test_size = 0.2, random_state = 42, stratify = y_data)
        
        train_x, train_y = self._convert_data(X_train, y_train)
        test_x, test_y = self._convert_data(X_test, y_test)
        
        return train_x, train_y, test_x, test_y

    def __init__(self):
        if not os.path.exists('./models'):
            os.mkdir('./models')
        
        self.DATASET_URL = "https://raw.githubusercontent.com/ukairia777/finance_sentiment_corpus/main/finance_data.csv"
        self.DATASET_NAME = "./models/finance_news_header.csv"
        self.DATASET_PREP_NAME = "./models/finance_news_header_prep.csv"
        self.MAX_SEQ_LEN = 64
        self.MODEL_NAME = "klue/bert-base"
        self.BEST_MODEL_NAME = './models/news_model.tf'
        
    def train_model(self):
        self.train_x, self.train_y, self.test_x, self.test_y = self._get_dataset()
        model = TFBertForSequenceClassification.from_pretrained(self.MODEL_NAME, num_labels=3, from_pt=True)
        token_inputs = tf.keras.layers.Input((self.MAX_SEQ_LEN,), dtype = tf.int32, name = 'input_word_ids')
        mask_inputs = tf.keras.layers.Input((self.MAX_SEQ_LEN,), dtype = tf.int32, name = 'input_masks')
        segment_inputs = tf.keras.layers.Input((self.MAX_SEQ_LEN,), dtype = tf.int32, name = 'input_segment')
        bert_outputs = model([token_inputs, mask_inputs, segment_inputs])
        bert_output = bert_outputs[0]
        
        DROPOUT_RATE = 0.5
        NUM_CLASS = 3
        dropout = tf.keras.layers.Dropout(DROPOUT_RATE)(bert_output)
        sentiment_layer = tf.keras.layers.Dense(NUM_CLASS, activation='softmax', kernel_initializer = tf.keras.initializers.TruncatedNormal(stddev=0.02))(dropout)
        sentiment_model = tf.keras.Model([token_inputs, mask_inputs, segment_inputs], sentiment_layer)
        
        OPTIMIZER_NAME = 'RAdam'
        LEARNING_RATE = 5e-5
        TOTAL_STEPS = 10000
        MIN_LR = 1e-5
        WARMUP_PROPORTION = 0.1
        EPSILON = 1e-8
        CLIPNORM = 1.0
        optimizer = tfa.optimizers.RectifiedAdam(learning_rate = LEARNING_RATE,total_steps = TOTAL_STEPS, warmup_proportion = WARMUP_PROPORTION, min_lr = MIN_LR, epsilon = EPSILON,clipnorm = CLIPNORM)
        sentiment_model.compile(optimizer = optimizer, loss = tf.keras.losses.SparseCategoricalCrossentropy(), metrics = ['accuracy'])
        
        MIN_DELTA = 1e-3
        PATIENCE = 5
        early_stopping = EarlyStopping(monitor = "val_accuracy", min_delta = MIN_DELTA, patience = PATIENCE)

        model_checkpoint = ModelCheckpoint(
            filepath = self.BEST_MODEL_NAME,
            monitor = "val_loss",
            mode = "min",
            save_best_only = True,
            verbose = 1
        )
        callbacks = [early_stopping, model_checkpoint]
        EPOCHS = 100
        BATCH_SZIE = 32
        
        sentiment_model.fit(self.train_x, self.train_y, epochs = EPOCHS, shuffle = True, batch_size = BATCH_SZIE, validation_data = (self.test_x, self.test_y), callbacks = callbacks) 
        self.model = sentiment_model
        
    def load_model(self):
        sentiment_model_best = tf.keras.models.load_model(self.BEST_MODEL_NAME,
                                                    custom_objects={'TFBertForSequenceClassification': TFBertForSequenceClassification})
        self.model = sentiment_model_best

    def analyze(self, data):
        return self.model.predict(data)

    def score(self, analyzed):
        weights = np.array([0, 0.7, -1.8])
        scores = np.dot(analyzed, weights)
        return scores
    
    def label(self, prediction):
        max_indices = np.argmax(prediction, axis=1)
        labels = ['neutral', 'positive', 'negative']
        labeled_data = [labels[idx] for idx in max_indices]
        return labeled_data
    
    def preprocess_x(self, data):
        def finance_pp(title):
            title = re.sub(r'[^a-zA-Z0-9가-힣\s]', '', title)
            title = title.replace('서프', '서프라이즈')
            title = re.sub(r'\[.*?\]', '', title)
            return title
            
        headlines = [finance_pp(p['title']) for p in data]
        
        tokenizer = self._get_BertTokenizer()
        tokens, masks, segments = [], [], []

        for X in tqdm(headlines):
            token = tokenizer.encode(X, truncation = True, padding = 'max_length', max_length = self.MAX_SEQ_LEN)
            num_zeros = token.count(0)
            mask = [1] * (self.MAX_SEQ_LEN - num_zeros) + [0] * num_zeros
            segment = [0]*self.MAX_SEQ_LEN
            tokens.append(token)
            masks.append(mask)
            segments.append(segment)
        tokens = np.array(tokens)
        masks = np.array(masks)
        segments = np.array(segments)
        return [tokens, masks, segments]
    
    def today_only(self, data):
        d = []
        for news in data:
            date = datetime.strptime(news['date'], "%Y.%m.%d %H:%M").date()
            if date == datetime.now().date():
                d.append(news)
        return d
    
    def get_news_by_page(self, symbol, n):
        url = f"https://finance.naver.com/item/news_news.naver?code={symbol}&page={n}&clusterId="
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        data = []
        for row in soup.select('tbody tr'):
            title = row.select_one('a').get_text(strip=True)
            date = row.select_one('td.date').get_text(strip=True)
            data.append({'title': title, 'date': date})
        return data