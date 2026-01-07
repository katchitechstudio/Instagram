import os
import time
import requests
import logging
import threading
import re
import json
from PIL import Image
from instagrapi import Client
from groq import Groq
from flask import Flask, request
from datetime import datetime
import pytz

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Değişkenler
instagram_status = "Beklemede..."
last_update = "Henüz işlem yapılmadı"

# Render Environment Variables
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
NEWSDATA_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "instagram-secret-2025")
SESSION_DATA = os.getenv("SESSION_DATA")

cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

# Sabit Cihaz Bilgisi
DEVICE_SETTINGS = {
    "app_version": "269.0.0.18.75",
    "android_version": 29,
    "android_release": "10.0",
    "dpi": "480dpi",
    "resolution": "1080x1920",
    "manufacturer": "Samsung",
    "device": "SM-G973F",
    "model": "Galaxy S10 Plus",
    "cpu": "exynos9820"
}

def remove_html_tags(text):
    if not text: return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(clean.split()).strip()

def truncate_text(text, max_length=400):
    if not text or len(text) <= max_length: return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."

# --- INSTAGRAM GİRİŞ (2FA DESTEKLİ) ---
def init_instagram():
    global instagram_status
    try:
        cl.set_device(DEVICE_SETTINGS)
        
        if SESSION_DATA:
            logger.info("SESSION_DATA kullanılarak oturum açılıyor...")
            try:
                # SESSION_DATA'yı dictionary olarak yükle
                session_settings = json.loads(SESSION_DATA)
                
                # load_settings() kullanarak oturumu yükle
                cl.load_settings(session_settings)
                
                # Oturumu test et
                cl.get_timeline_feed()
                instagram_status = "Bağlı (Oturum Onaylı) ✅"
                logger.info("Instagram oturumu başarıyla doğrulandı.")
                return
                
            except Exception as session_err:
                logger.warning(f"Oturum geçersiz veya hatalı: {session_err}")
                logger.info("Normal kullanıcı adı/şifre ile giriş yapılıyor...")
        
        # 2FA kontrolü - environment variable'dan kod al
        verification_code = os.getenv("VERIFICATION_CODE", "").strip()
        
        if verification_code:
            logger.info("2FA kodu environment variable'dan alındı, giriş yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, verification_code=verification_code)
        else:
            logger.info("Normal giriş deneniyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        
        instagram_status = "Bağlı (Yeni Giriş) ✅"
        logger.info("Instagram'a başarıyla giriş yapıldı.")
        
        # Yeni oturum verilerini kaydet (konsola yazdır)
        new_session = cl.get_settings()
        logger.info("=" * 60)
        logger.info("YENİ SESSION_DATA (Render'a kaydedin):")
        logger.info(json.dumps(new_session))
        logger.info("=" * 60)
        
    except Exception as e:
        instagram_status = f"Giriş Hatası: {str(e)[:100]} ❌"
        logger.error(f"Instagram Login Hatası: {e}", exc_info=True)
        
        # 2FA hatası için özel mesaj
        if "Two-factor authentication required" in str(e):
            logger.error("=" * 60)
            logger.error("2FA GEREKLİ! Şu adımları izleyin:")
            logger.error("1. Instagram'dan gelen SMS/Email kodunu alın")
            logger.error("2. Render'da VERIFICATION_CODE environment variable'ı ekleyin")
            logger.error("3. Değer olarak 6 haneli kodu girin")
            logger.error("4. Servisi yeniden başlatın")
            logger.error("=" * 60)

# --- HABER ÇEKME ---
def get_latest_news():
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q=haber&country=tr&language=tr"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if data.get("status") == "success" and data.get("results"):
            for news in data["results"]:
                if news.get("image_url"):
                    return news
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
    return None

# --- GÖRSEL HAZIRLAMA ---
def create_instagram_post(news_item):
    img_url = news_item.get("image_url")
    img_path = "news_image.jpg"
    final_path = "final_post.jpg"
    try:
        r = requests.get(img_url, timeout=15)
        with open(img_path, "wb") as f:
            f.write(r.content)
        
        img = Image.open(img_path).convert("RGB")
        img = img.resize((1080, 1350)) 
        
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            logo.thumbnail((150, 150))
            img.paste(logo, (50, 50), logo)
            
        img.save(final_path, "JPEG", quality=95)
        return final_path
    except Exception as e:
        logger.error(f"Görsel işleme hatası: {e}")
        return None

# --- AI AÇIKLAMA ---
def generate_ai_caption(title, description):
    try:
        clean_title = remove_html_tags(title)
        clean_desc = truncate_text(remove_html_tags(description or ""), 300)
        prompt = f"Haber Başlığı: {clean_title}\nİçerik: {clean_desc}\n\nBu haberi Instagram'da paylaşacağım. Dikkat çekici, kısa bir açıklama yaz ve uygun hashtagler ekle."
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception:
        return f"🚨 {title}\n\nDetaylar biyografide! #haber #sondakika"

# --- ANA GÖREV ---
def job():
    global last_update, instagram_status
    tz = pytz.timezone('Europe/Istanbul')
    last_update = datetime.now(tz).strftime('%d/%m/%Y %H:%M:%S')
    
    logger.info("Süreç başladı...")
    news = get_latest_news()
    
    if not news:
        logger.warning("Paylaşılacak yeni haber bulunamadı.")
        return

    init_instagram()
    
    if "Bağlı" in instagram_status:
        image_path = create_instagram_post(news)
        if image_path:
            caption = generate_ai_caption(news['title'], news.get('description', ''))
            try:
                cl.photo_upload(image_path, caption)
                logger.info("Paylaşım Instagram'a başarıyla gönderildi!")
                instagram_status = "Son Paylaşım Başarılı ✅"
            except Exception as e:
                logger.error(f"Upload hatası: {e}")
                instagram_status = "Paylaşım Hatası ❌"
        else:
            logger.error("Görsel hazırlanamadığı için iptal edildi.")

# --- WEB PANEL VE TETİKLEYİCİ ---
@app.route('/')
def home():
    return f"""
    <html>
        <body style="font-family:sans-serif; text-align:center; padding:50px;">
            <h1>Haber Botu Kontrol Paneli</h1>
            <p><strong>Durum:</strong> {instagram_status}</p>
            <p><strong>Son İşlem:</strong> {last_update}</p>
            <hr>
            <p><a href="/run?key={SECRET_KEY}">HABER PAYLAŞIMINI ŞİMDİ TETİKLE</a></p>
        </body>
    </html>
    """

@app.route('/run')
def manual_run():
    key = request.args.get('key')
    if key != SECRET_KEY:
        return "Hatalı Şifre!", 403
    
    thread = threading.Thread(target=job)
    thread.start()
    return "Bot uyanıyor, haber paylaşım işlemi başlatıldı... 1 dakika içinde Instagram'ı kontrol edin.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
