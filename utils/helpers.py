import os
import time
import requests
import logging
import threading
import re
from PIL import Image
from instagrapi import Client
from groq import Groq
from flask import Flask, request
from datetime import datetime
import pytz

# --- LOGLAMA VE AYARLAR ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Panel Değişkenleri
instagram_status = "Hazır (Tetikleme Bekliyor)"
last_update = "Henüz işlem yapılmadı"

# Render Environment Variables
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
NEWSDATA_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "haber123") # Buraya Render'dan verdiğin şifreyi yaz

cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

# --- SENİN GÖNDERDİĞİN GELİŞMİŞ TEMİZLEME FONKSİYONLARI ---

def clean_text(text: str) -> str:
    if not text: return ""
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = " ".join(text.split())
    return text.strip()

def truncate_text(text: str, max_length: int = 350, suffix: str = "...") -> str:
    if not text or len(text) <= max_length: return text
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + suffix

def remove_html_tags(text: str) -> str:
    if not text: return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
    clean = clean.replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return clean_text(clean)

# --- BOT MANTIĞI ---

def init_instagram():
    global instagram_status
    try:
        # Cihaz ayarlarını sabitliyoruz (Ban riskini azaltır)
        cl.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 30,
            "android_release": "11.0",
            "dpi": "440dpi",
            "resolution": "1080x2340",
            "manufacturer": "OnePlus",
            "device": "6T",
            "model": "ONEPLUS A6010",
            "cpu": "qcom"
        })
        logger.info("Instagram'a giriş denemesi yapılıyor...")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        instagram_status = "Bağlı ✅"
    except Exception as e:
        instagram_status = f"Giriş Hatası: {str(e)[:50]} ❌"
        logger.error(f"Giriş hatası: {e}")

def get_latest_news():
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q=haber&country=tr&language=tr"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if data.get("status") == "success" and data.get("results"):
            # Görseli olan ilk haberi bulalım
            for item in data["results"]:
                if item.get("image_url"):
                    return item
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
    return None

def create_instagram_post(news_item):
    img_url = news_item.get("image_url")
    final_path = "final_post.jpg"
    try:
        r = requests.get(img_url, timeout=15)
        with open("temp_img.jpg", "wb") as f:
            f.write(r.content)
        
        img = Image.open("temp_img.jpg").convert("RGB")
        img = img.resize((1080, 1350)) # Portrait oran
        
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            logo.thumbnail((180, 180))
            img.paste(logo, (50, 50), logo)
            
        img.save(final_path, "JPEG", quality=95)
        return final_path
    except Exception as e:
        logger.error(f"Görsel oluşturma hatası: {e}")
        return None

def generate_ai_caption(title, description):
    try:
        clean_title = remove_html_tags(title)
        clean_desc = truncate_text(remove_html_tags(description or ""), 300)
        
        prompt = f"Haber: {clean_title}\nDetay: {clean_desc}\n\nBu haberi Instagram'da paylaşacağım. Kısa, merak uyandırıcı, emojili bir açıklama ve 3-5 adet hashtag yaz."
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception:
        return f"🚨 {title}\n\nDetaylar için takipte kalın. #haber #sondakika"

def job():
    global last_update, instagram_status
    tz = pytz.timezone('Europe/Istanbul')
    last_update = datetime.now(tz).strftime('%H:%M:%S')
    
    news = get_latest_news()
    if news:
        init_instagram()
        if "Bağlı" in instagram_status:
            img_path = create_instagram_post(news)
            if img_path:
                caption = generate_ai_caption(news['title'], news.get('description', ''))
                try:
                    cl.photo_upload(img_path, caption)
                    instagram_status = "Paylaşım Başarılı ✅"
                    logger.info("Paylaşıldı!")
                except Exception as e:
                    instagram_status = "Paylaşım Hatası ❌"
                    logger.error(f"Upload hatası: {e}")
    else:
        logger.warning("Görselli haber bulunamadı.")

# --- WEB PANEL VE TETİKLEME ---

@app.route('/')
def home():
    return f"""
    <html>
        <head><title>Haber Botu</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Instagram Haber Botu</h1>
            <p><strong>Durum:</strong> {instagram_status}</p>
            <p><strong>Son Tetiklenme:</strong> {last_update}</p>
            <hr>
            <p>Çalıştırmak için gizli linkini kullanın.</p>
        </body>
    </html>
    """

@app.route('/run')
def run_trigger():
    key = request.args.get('key')
    if key != SECRET_KEY:
        return "Yetkisiz erişim!", 403
    
    # Arka planda çalıştır ki sayfa hemen yüklensin
    thread = threading.Thread(target=job)
    thread.start()
    return "Bot tetiklendi! 1 dakika içinde Instagram'ı kontrol edin.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
