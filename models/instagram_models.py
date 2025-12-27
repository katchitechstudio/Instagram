
from datetime import datetime, timedelta
from config import Config
from models.db import get_db, put_db
import logging
import pytz
import hashlib

logger = logging.getLogger(__name__)


class InstagramModel:

    @staticmethod
    def create_table():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS instagram_posts (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    summary TEXT,
                    image_url TEXT,
                    source_url TEXT,
                    category VARCHAR(50),
                    posted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    posted_at TIMESTAMPTZ,
                    title_hash VARCHAR(64) UNIQUE
                );
                
                CREATE TABLE IF NOT EXISTS instagram_stats (
                    id SERIAL PRIMARY KEY,
                    today_posts INTEGER DEFAULT 0,
                    total_posts INTEGER DEFAULT 0,
                    daily_limit INTEGER DEFAULT 15,
                    last_post_date DATE,
                    updated_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC')
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_instagram_posts_created 
                ON instagram_posts(created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_instagram_posts_posted 
                ON instagram_posts(posted);
                
                CREATE INDEX IF NOT EXISTS idx_instagram_posts_hash 
                ON instagram_posts(title_hash);
            """)
            
            cur.execute("""
                INSERT INTO instagram_stats (id, today_posts, total_posts, daily_limit)
                VALUES (1, 0, 0, 15)
                ON CONFLICT (id) DO NOTHING;
            """)

            conn.commit()
            logger.info("instagram_posts tablosu hazır")

        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                put_db(conn)

    @staticmethod
    def _generate_hash(title: str) -> str:
        return hashlib.md5(title.lower().strip().encode('utf-8')).hexdigest()

    @staticmethod
    def save_post(post_data: dict) -> bool:
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            now_utc = datetime.now(pytz.UTC)

            title = post_data.get('title', '').strip()
            description = post_data.get('description', '').strip()
            summary = post_data.get('summary', '').strip()
            image_url = post_data.get('image_url', '').strip()
            source_url = post_data.get('source_url', '').strip()
            category = post_data.get('category', 'teknoloji')

            if not title or not summary:
                logger.warning("Boş title veya summary")
                return False

            title_hash = InstagramModel._generate_hash(title)

            cur.execute("""
                INSERT INTO instagram_posts (
                    title, description, summary, image_url, source_url, category, title_hash, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title_hash) DO NOTHING
                RETURNING id;
            """, (
                title, description, summary, image_url, source_url, category, title_hash, now_utc
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                logger.debug(f"Post kaydedildi: {title[:50]}...")
                return True
            else:
                logger.debug(f"Duplicate atlandı: {title[:50]}...")
                return False

        except Exception as e:
            logger.error(f"Post kaydedilemedi: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            if conn:
                put_db(conn)

    @staticmethod
    def get_unposted_posts(limit: int = 15):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                SELECT id, title, summary, image_url, category, created_at
                FROM instagram_posts
                WHERE posted = FALSE
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))

            rows = cur.fetchall()

            posts = []
            for r in rows:
                posts.append({
                    "id": r[0],
                    "title": r[1],
                    "summary": r[2],
                    "image_url": r[3],
                    "category": r[4],
                    "created_at": r[5].isoformat() if r[5] else None
                })

            return posts

        except Exception as e:
            logger.exception("get_unposted_posts hatası")
            return []
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def mark_as_posted(post_id: int):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            now_utc = datetime.now(pytz.UTC)

            cur.execute("""
                UPDATE instagram_posts
                SET posted = TRUE, posted_at = %s
                WHERE id = %s;
            """, (now_utc, post_id))

            conn.commit()
            logger.info(f"Post {post_id} posted olarak işaretlendi")

        except Exception as e:
            logger.error(f"mark_as_posted hatası: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_stats():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                SELECT today_posts, total_posts, daily_limit, last_post_date
                FROM instagram_stats
                WHERE id = 1;
            """)

            result = cur.fetchone()

            if result:
                return {
                    "today_posts": result[0],
                    "total_posts": result[1],
                    "daily_limit": result[2],
                    "last_post_date": result[3].isoformat() if result[3] else None
                }

            return {"today_posts": 0, "total_posts": 0, "daily_limit": 15, "last_post_date": None}

        except Exception as e:
            logger.error(f"get_stats hatası: {e}")
            return {"today_posts": 0, "total_posts": 0, "daily_limit": 15, "last_post_date": None}
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def increment_stats():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            now_utc = datetime.now(pytz.UTC)
            today = now_utc.date()

            cur.execute("""
                SELECT last_post_date FROM instagram_stats WHERE id = 1;
            """)

            result = cur.fetchone()
            last_date = result[0] if result else None

            if last_date != today:
                cur.execute("""
                    UPDATE instagram_stats
                    SET today_posts = 1, total_posts = total_posts + 1, last_post_date = %s, updated_at = %s
                    WHERE id = 1;
                """, (today, now_utc))
            else:
                cur.execute("""
                    UPDATE instagram_stats
                    SET today_posts = today_posts + 1, total_posts = total_posts + 1, updated_at = %s
                    WHERE id = 1;
                """, (now_utc,))

            conn.commit()

        except Exception as e:
            logger.error(f"increment_stats hatası: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def can_post_today():
        stats = InstagramModel.get_stats()
        return stats["today_posts"] < stats["daily_limit"]

    @staticmethod
    def get_total_count():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM instagram_posts;")
            result = cur.fetchone()
            return result[0] if result else 0

        except Exception as e:
            logger.exception("get_total_count hatası")
            return 0
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)
