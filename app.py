import os
import time
import requests
import logging
import threading
from PIL import Image
from instagrapi import Client
from groq import Groq
from flask import Flask

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Durum takibi için global değişkenler
instagram_status = "Başlatılmadı"
last_update = "Henüz işlem yapılmadı"

# Config yükleme
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
NEWSDATA_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

@app.route('/')
def health_check():
    # Tarayıcıda botun ve Instagram'ın durumunu gösterir
    return f"""
    <h1>Bot Durum Paneli</h1>
    <p><strong>Bot Durumu:</strong> Aktif ✅</p>
    <p><strong>Instagram Durumu:</strong> {instagram_status}</p>
    <p><strong>Son İşlem Zamanı:</strong> {last_update}</p>
    <hr>
    <p>Eğer durum 'Hata' ise Render loglarını kontrol edin.</p>
    """, 200

def init_instagram():
    global instagram_status
    try:
        session_file = "session.json"
        if os.path.exists(session_file):
            logger.info("Session dosyası yükleniyor...")
            cl.load_settings(session_file)
            
            try:
                cl.get_timeline_feed() 
                logger.info("Mevcut oturum geçerli.")
                instagram_status = "Bağlı (Session ile) ✅"
                return
            except Exception:
                logger.warning("Session geçersizleşmiş.")

        if not cl.user_id:
            logger.info("Instagram girişi yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(session_file)
            logger.info("Giriş başarılı!")
            instagram_status = "Bağlı (Yeni Giriş) ✅"
            
    except Exception as e:
        error_msg = str(e)
        if "blacklist" in error_msg.lower():
            instagram_status = "Hata: IP Yasaklı (Blacklist) ❌"
        elif "login_required" in error_msg.lower():
            instagram_status = "Hata: Giriş Gerekli (Session Geçersiz) ❌"
        else:
            instagram_status = f"Hata: {error_msg[:50]}... ❌"
        logger.error(f"Instagram giriş hatası: {e}")

# ... (get_latest_news, create_instagram_post, generate_ai_caption fonksiyonları aynı kalacak)

def job():
    global last_update
    last_update = time.strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"Süreç başlatılıyor... Saat: {last_update}")
    
    news = get_latest_news()
    if news:
        init_instagram()
        if "Bağlı" in instagram_status:
            image_path = create_instagram_post(news)
            if image_path:
                caption = generate_ai_caption(news['title'], news.get('description', ''))
                try:
                    cl.photo_upload(image_path, caption)
                    logger.info("Instagram paylaşımı başarıyla yapıldı!")
                except Exception as e:
                    logger.error(f"Paylaşım hatası: {e}")
    else:
        logger.warning("Yeni haber bulunamadı.")

def run_bot_loop():
    while True:
        job()
        # Test için burayı 60 (1 dakika) yapabilirsin, 
        # her şeyin çalıştığından emin olunca 14400 (4 saat) yaparsın.
        time.sleep(14400)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
