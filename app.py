import os
import time
import requests
import logging
import threading
from PIL import Image
from instagrapi import Client
from groq import Groq
from flask import Flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
NEWSDATA_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

@app.route('/')
def health_check():
    return "Bot is active", 200

def init_instagram():
    try:
        # 1. Önce yüklü olan session.json dosyasını kontrol et
        if os.path.exists("session.json"):
            logger.info("Session dosyası bulundu, yükleniyor...")
            cl.load_settings("session.json")
            
            try:
                # Oturumun geçerliliğini test et
                cl.get_timeline_feed() 
                logger.info("Mevcut oturum geçerli.")
                return
            except Exception:
                logger.warning("Session geçersizleşmiş, yeniden giriş denenecek.")

        # 2. Session yoksa veya geçersizse login ol
        if not cl.user_id:
            logger.info("Instagram girişi yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings("session.json")
            logger.info("Instagram girişi başarılı ve yeni session kaydedildi!")
    except Exception as e:
        logger.error(f"Instagram giriş hatası: {e}")

def get_latest_news():
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q=haber&country=tr&language=tr"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("status") == "success" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
    return None

def create_instagram_post(news_item):
    img_url = news_item.get("image_url")
    if not img_url: return None
    img_path = "news_image.jpg"
    final_path = "final_post.jpg"
    try:
        with open(img_path, "wb") as f:
            f.write(requests.get(img_url).content)
        img = Image.open(img_path).convert("RGB")
        img = img.resize((1080, 1350))
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            logo.thumbnail((200, 200))
            img.paste(logo, (50, 50), logo)
        img.save(final_path, "JPEG", quality=95)
        return final_path
    except Exception as e:
        logger.error(f"Görsel oluşturma hatası: {e}")
        return None

def generate_ai_caption(title, description):
    try:
        prompt = f"Şu haberi etkileyici bir Instagram gönderisi haline getir:\nBaşlık: {title}\nDetay: {description}\nKısa, çarpıcı ve emojili olsun."
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192", # Hatalı model ismi güncellendi
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API hatası: {e}")
        return f"{title}\n\nDetaylar için takipte kalın! #haber"

def job():
    logger.info("Süreç başlatılıyor...")
    news = get_latest_news()
    if news:
        init_instagram()
        image_path = create_instagram_post(news)
        if image_path:
            caption = generate_ai_caption(news['title'], news.get('description', ''))
            try:
                # Paylaşım öncesi oturum kontrolü
                cl.photo_upload(image_path, caption)
                logger.info("Instagram paylaşımı başarıyla yapıldı!")
            except Exception as e:
                logger.error(f"Paylaşım hatası: {e}")
    else:
        logger.warning("Yeni haber bulunamadı.")

def run_bot_loop():
    while True:
        job()
        logger.info("4 saat bekleniyor...")
        time.sleep(14400)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
