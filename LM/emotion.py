from transformers import BertTokenizer, BertForSequenceClassification, pipeline

def get_model():
    model_name = "beomi/kcbert-base"
    tokenizer = BertTokenizer.from_pretrained(model_name)
    model = BertForSequenceClassification.from_pretrained(model_name)
    sentiment_analysis = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
    return sentiment_analysis

def get_analysis(model, preprocessed_headlines):
    results = model(preprocessed_headlines)
    for headline, result in zip(preprocessed_headlines, results):
        print(f"헤드라인: {headline} => 감정: {result['label']}, 점수: {result['score']}")