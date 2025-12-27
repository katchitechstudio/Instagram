from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models.instagram_models import InstagramModel
from models.db import init_connection_pool
from routes.instagram_routes import instagram_bp
from services.instagram_service import InstagramService
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import os
from datetime import datetime, timedelta
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, resources={r"/*": {"origins": "*"}})

try:
    init_connection_pool()
    InstagramModel.create_table()
    logger.info("Database başlatıldı")
except Exception as e:
    logger.error(f"Database başlatma hatası: {e}")

app.register_blueprint(instagram_bp)

scheduler = BackgroundScheduler(timezone=pytz.timezone(Config.TIMEZONE))

scheduler.add_job(
    func=InstagramService.auto_post_scheduler,
    trigger='interval',
    hours=2,
    id='auto_instagram',
    next_run_time=datetime.now() + timedelta(minutes=10)
)

scheduler.start()
logger.info("Instagram otomatik paylaşım aktif (her 2 saatte)")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "instagram-automation",
        "timestamp": datetime.now(pytz.UTC).isoformat()
    }), 200


@app.route("/", methods=["GET"])
def home():
    stats = InstagramModel.get_stats()
    
    return jsonify({
        "message": "Instagram Automation API",
        "status": "running",
        "stats": stats
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info("Instagram Automation starting...")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
