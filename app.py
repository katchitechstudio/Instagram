import os
import time
import requests
import logging
from PIL import Image
from instagrapi import Client
from groq import Groq

# Logging Ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Render Environment Variables üzerinden bilgileri alıyoruz
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
# Senin Render'da yazdığın isme (NEWS_API_KEY) göre güncelledim:
NEWSDATA_API_KEY = os.getenv("NEWS_API_KEY") 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# API İstemcileri
cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

def init_instagram():
    try:
        if not cl.user_id:
            if os.path.exists("session.json"):
                logger.info("Session dosyası bulundu, oturum yükleniyor...")
                cl.load_settings("session.json")
            
            logger.info("Instagram girişi yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            logger.info("Instagram girişi başarılı!")
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
            model="llama-3.1-70b-versatile",
        )
        return chat_completion.choices[0].message.content
    except Exception:
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
                cl.photo_upload(image_path, caption)
                logger.info("Instagram paylaşımı başarıyla yapıldı!")
            except Exception as e:
                logger.error(f"Paylaşım hatası: {e}")
    else:
        logger.warning("Yeni haber bulunamadı.")

if __name__ == "__main__":
    while True:
        job()
        logger.info("4 saat bekleniyor...")
        time.sleep(14400)
