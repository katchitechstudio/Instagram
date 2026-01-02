import os
import logging
import requests
import pytz
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from groq import Groq
from instagrapi import Client
from PIL import Image, ImageEnhance
# utils/helpers.py içindeki temizlik araçlarını çağırıyoruz
from utils.helpers import remove_html_tags, clean_text 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Yapılandırma
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Istanbul')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

cl = Client()

def init_instagram():
    try:
        if not cl.user_id:
            logger.info("Instagram girişi yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            logger.info("Instagram girişi başarılı!")
    except Exception as e:
        logger.error(f"Instagram giriş hatası: {e}")

def process_image(input_path, output_path):
    try:
        base_image = Image.open(input_path).convert("RGBA")
        enhancer = ImageEnhance.Brightness(base_image)
        base_image = enhancer.enhance(0.85) # %15 Karartma

        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            base_w, base_h = base_image.size
            new_logo_w = int(base_w * 0.15)
            w_percent = (new_logo_w / float(logo.size[0]))
            new_logo_h = int((float(logo.size[1]) * float(w_percent)))
            logo = logo.resize((new_logo_w, new_logo_h), Image.Resampling.LANCZOS)
            position = (base_w - new_logo_w - 25, base_h - new_logo_h - 25)
            base_image.paste(logo, position, logo)
        
        final_image = base_image.convert("RGB")
        final_image.save(output_path, "JPEG", quality=90)
        return True
    except Exception as e:
        logger.error(f"Görsel işleme hatası: {e}")
        return False

def post_to_instagram():
    logger.info("Otomatik paylaşım süreci başladı...")
    try:
        init_instagram()
        # Senin NewsData API anahtarın için doğru URL:
        news_url = f'https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&country=tr&language=tr'
        res = requests.get(news_url).json()
        
        if res.get('results'):
            article = res['results'][0]
            # Senin Helpers dosyanı burada kullanıyoruz:
            raw_title = article.get('title', '')
            raw_desc = article.get('description', 'Detaylar haberimizde.')
            
            clean_title = clean_text(remove_html_tags(raw_title))
            clean_desc = clean_text(remove_html_tags(raw_desc))
            
            img_url = article.get('image_url')
            
            if img_url:
                img_data = requests.get(img_url).content
                with open("raw.jpg", "wb") as f:
                    f.write(img_data)
                
                if process_image("raw.jpg", "final.jpg"):
                    # Groq ile Caption Oluşturma
                    client = Groq(api_key=GROQ_API_KEY)
                    prompt = f"Instagram için kısa, ilgi çekici bir haber bülteni yaz. Başlık: {clean_title} Detay: {clean_desc}"
                    
                    completion = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    caption = completion.choices[0].message.content
                    
                    cl.photo_upload("final.jpg", caption)
                    logger.info("Instagram paylaşımı başarılı!")
                
                for f in ["raw.jpg", "final.jpg"]:
                    if os.path.exists(f): os.remove(f)
    except Exception as e:
        logger.error(f"Süreç hatası: {e}")

# Zamanlayıcı: Bot açılır açılmaz çalışır, sonra her 2 saatte bir devam eder.
scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))
scheduler.add_job(
    func=post_to_instagram, 
    trigger='interval', 
    hours=2, 
    next_run_time=datetime.now(pytz.timezone(TIMEZONE))
)
scheduler.start()

@app.route('/')
def home():
    return f"Habersel Bot Aktif. Saat: {datetime.now()}"

@app.route('/health')
def health():
    return jsonify(status="up"), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
