from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
import logging
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "instagram-automation",
        "timestamp": datetime.now(pytz.UTC).isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Instagram Automation API",
        "status": "running"
    }), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info("Instagram Automation starting...")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
