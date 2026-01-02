import os
import time
import requests
import logging
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client
from groq import Groq
from config import *

# Logging Ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API İstemcileri
cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

def init_instagram():
    """Instagram'a session dosyası veya şifre ile giriş yapar."""
    try:
        if not cl.user_id:
            # GitHub'a yüklediğin session.json dosyasını kontrol eder
            if os.path.exists("session.json"):
                logger.info("Session dosyası bulundu, oturum yükleniyor...")
                cl.load_settings("session.json")
                try:
                    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                except Exception as e:
                    logger.warning(f"Session geçersiz, normal giriş deneniyor: {e}")
                    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            else:
                logger.info("Session dosyası yok, normal giriş yapılıyor...")
                cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            
            logger.info("Instagram girişi başarılı!")
    except Exception as e:
        logger.error(f"Instagram giriş hatası: {e}")

def get_latest_news():
    """NewsData.io üzerinden güncel haberleri çeker."""
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q=haber&country=tr&language=tr"
    response = requests.get(url)
    data = response.json()
    if data.get("status") == "success" and data.get("results"):
        return data["results"][0]
    return None

def create_instagram_post(news_item):
    """Haber görseli ve logoyu birleştirir."""
    img_url = news_item.get("image_url")
    if not img_url:
        return None

    # Görseli indir
    img_path = "news_image.jpg"
    with open(img_path, "wb") as f:
        f.write(requests.get(img_url).content)

    # Görsel işleme
    img = Image.open(img_path).convert("RGB")
    img = img.resize((1080, 1350)) # Instagram Portrait formatı

    # Logoyu ekle (logo.png dosyan GitHub'da var)
    if os.path.exists("logo.png"):
        logo = Image.open("logo.png").convert("RGBA")
        logo.thumbnail((200, 200)) # Logo boyutu
        img.paste(logo, (50, 50), logo) # Sol üst köşeye yapıştır

    final_path = "final_post.jpg"
    img.save(final_path, quality=95)
    return final_path

def generate_ai_caption(title, description):
    """Groq AI ile etkileyici açıklama oluşturur."""
    prompt = f"Şu haberi etkileyici bir Instagram gönderisi haline getir:\nBaşlık: {title}\nDetay: {description}\nKısa, çarpıcı ve emojili olsun."
    
    chat_completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-70b-versatile",
    )
    return chat_completion.choices[0].message.content

def job():
    """Ana döngü: Haber çek, görsel oluştur, paylaş."""
    logger.info("Haber kontrolü başlatılıyor...")
    news = get_latest_news()
    
    if news:
        logger.info(f"Haber bulundu: {news['title']}")
        init_instagram()
        
        image_path = create_instagram_post(news)
        if image_path:
            caption = generate_ai_caption(news['title'], news.get('description', ''))
            
            try:
                cl.photo_upload(image_path, caption)
                logger.info("Instagram paylaşımı başarılı!")
            except Exception as e:
                logger.error(f"Paylaşım hatası: {e}")
        else:
            logger.warning("Haber görseli bulunamadı, geçiliyor.")
    else:
        logger.warning("Yeni haber bulunamadı.")

if __name__ == "__main__":
    # Render'da botun sürekli çalışması için döngü
    while True:
        try:
            job()
        except Exception as e:
            logger.error(f"Genel hata: {e}")
        
        logger.info("2 saat bekleniyor...")
        time.sleep(7200) # 2 saatte bir çalışır
