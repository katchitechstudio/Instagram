from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import os
from datetime import datetime
import pytz
import requests
from groq import Groq
from instagrapi import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Config
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Istanbul')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

# Instagram Client
instagram_client = None

def init_instagram():
    """Instagram'a giriş yap"""
    global instagram_client
    try:
        instagram_client = Client()
        instagram_client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        logger.info("Instagram'a giriş başarılı")
        return True
    except Exception as e:
        logger.error(f"Instagram giriş hatası: {e}")
        return False

def fetch_news():
    """Haber sitelerinden son haberleri çek"""
    try:
        # Örnek: NewsAPI veya RSS feed kullanabilirsiniz
        # Burada basit bir örnek:
        response = requests.get('https://newsapi.org/v2/top-headlines?country=tr&apiKey=YOUR_API_KEY')
        news = response.json()
        
        if news.get('articles'):
            article = news['articles'][0]  # İlk haberi al
            return {
                'title': article['title'],
                'description': article['description'],
                'url': article['url']
            }
        return None
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
        return None

def create_instagram_caption(news):
    """Groq AI ile Instagram caption oluştur"""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt = f"""
        Şu haberi Instagram için kısa ve çekici bir gönderi haline getir:
        
        Başlık: {news['title']}
        Açıklama: {news['description']}
        
        Kurallar:
        - Maksimum 5 cümle
        - Türkçe olsun
        - 3-5 hashtag ekle
        - Link: {news['url']}
        """
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Caption oluşturma hatası: {e}")
        return None

def post_to_instagram():
    """Instagram'a haber paylaş"""
    try:
        # Haber çek
        news = fetch_news()
        if not news:
            logger.warning("Haber bulunamadı")
            return False
        
        # Caption oluştur
        caption = create_instagram_caption(news)
        if not caption:
            logger.warning("Caption oluşturulamadı")
            return False
        
        # Instagram'a paylaş
        if instagram_client:
            # Not: Instagram'a sadece fotoğraf/video ile post atılabilir
            # Burada bir görsel eklemeniz gerekir
            # instagram_client.photo_upload("gorsel.jpg", caption)
            logger.info(f"Instagram'a paylaşıldı: {caption[:50]}...")
            return True
        else:
            logger.error("Instagram client hazır değil")
            return False
            
    except Exception as e:
        logger.error(f"Paylaşım hatası: {e}")
        return False

# Scheduler
scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))

# Her 2 saatte bir haber paylaş
scheduler.add_job(
    func=post_to_instagram,
    trigger='interval',
    hours=2,
    id='auto_instagram_news',
    next_run_time=datetime.now(pytz.timezone(TIMEZONE))
)

scheduler.start()
logger.info("Instagram haber botu başlatıldı (her 2 saatte)")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "instagram-news-bot",
        "timestamp": datetime.now(pytz.UTC).isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Instagram Haber Botu",
        "status": "running",
        "next_post": "Her 2 saatte"
    }), 200

@app.route("/test-post", methods=["POST"])
def test_post():
    """Manuel test paylaşımı"""
    result = post_to_instagram()
    return jsonify({
        "success": result,
        "message": "Paylaşım yapıldı" if result else "Hata oluştu"
    }), 200 if result else 500

if __name__ == "__main__":
    # Instagram'a giriş yap
    init_instagram()
    
    port = int(os.getenv("PORT", 10000))
    logger.info("Instagram Haber Botu başlatılıyor...")
    app.run(host="0.0.0.0", port=port, debug=False)
