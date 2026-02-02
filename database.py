"""
مدیریت دیتابیس با SQLite

"""
import sqlite3
import json
import threading
import atexit
from logger import log_database_operation, log_error
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from contextlib import contextmanager
from config import DATABASE_NAME
import logging
import pytz

logger = logging.getLogger(__name__)

# Timezone تهران
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

def get_tehran_now():
    """دریافت زمان فعلی تهران"""
    return datetime.now(TEHRAN_TZ)


class DatabaseConnectionPool:
    """مدیریت Connection Pool برای دیتابیس"""
    
    def __init__(self, database_name: str):
        self.database_name = database_name
        self._local = threading.local()
        self._lock = threading.Lock()
        self._active_connections = []
        
        atexit.register(self.cleanup_all)
        
    def get_connection(self) -> sqlite3.Connection:
        """دریافت connection برای thread فعلی"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            try:
                conn = sqlite3.connect(
                    self.database_name,
                    timeout=30.0,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                
                self._local.connection = conn
                
                with self._lock:
                    self._active_connections.append(conn)
                
                logger.debug(f"✅ Connection created for thread {threading.current_thread().name}")
            except sqlite3.Error as e:
                logger.error(f"❌ Failed to create connection: {e}")
                raise
        
        return self._local.connection
    
    def close_connection(self):
        """بستن connection thread فعلی"""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            try:
                self._local.connection.close()
                
                with self._lock:
                    if self._local.connection in self._active_connections:
                        self._active_connections.remove(self._local.connection)
                
                logger.debug(f"✅ Connection closed for thread {threading.current_thread().name}")
            except sqlite3.Error as e:
                logger.error(f"❌ Failed to close connection: {e}")
            finally:
                self._local.connection = None
    
    def cleanup_all(self):
        """بستن تمام connection‌های فعال"""
        logger.info("🧹 Cleaning up all database connections...")
        
        with self._lock:
            for conn in self._active_connections[:]:
                try:
                    conn.close()
                    logger.debug(f"✅ Connection closed during cleanup")
                except Exception as e:
                    logger.error(f"❌ Error closing connection: {e}")
            
            self._active_connections.clear()
        
        logger.info("✅ All connections cleaned up")


class DatabaseError(Exception):
    """خطای عملیات دیتابیس"""
    pass


class Database:
    """کلاس مدیریت دیتابیس با امنیت بالا"""

    def __init__(self, cache_manager=None):
        """✅ FIX: حذف self.conn و self.cursor سراسری"""
        self.pool = DatabaseConnectionPool(DATABASE_NAME)
        self.cache_manager = cache_manager
        self.create_tables()
        
        logger.info("✅ Database initialized successfully")
    
    def _get_conn(self) -> sqlite3.Connection:
        """دریافت connection برای thread فعلی"""
        return self.pool.get_connection()
    
    def _sanitize_text_input(self, text: str, max_length: int = None) -> str:
        """
        ✅ NEW: پاکسازی ورودی متنی
        """
        if text is None:
            return None
        
        text = text.strip()
        
        if max_length and len(text) > max_length:
            text = text[:max_length]
        
        return text
    
    @contextmanager
    def transaction(self):
        """Context Manager برای تراکنش‌های دیتابیس"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN")
            yield cursor
            conn.commit()
            logger.debug("✅ Transaction committed")
        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.error(f"❌ IntegrityError: {e}")
            raise DatabaseError(f"خطای یکپارچگی داده: {e}")
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"❌ OperationalError: {e}")
            raise DatabaseError(f"خطای عملیاتی: {e}")
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Transaction failed: {e}")
            raise DatabaseError(f"خطای تراکنش: {e}")
    
    def _invalidate_cache(self, pattern: str):
        """حذف کش مرتبط"""
        if self.cache_manager:
            self.cache_manager.invalidate_pattern(pattern)
    
    def clean_invalid_cart_items(self, user_id: int):
        """
        حذف آیتم‌های نامعتبر از سبد
        ✅ FIX: این تابع دیگه خودکار صدا زده نمیشه
        """
        try:
            with self.transaction() as cursor:
                cursor.execute("""
                    DELETE FROM cart 
                    WHERE user_id = ? 
                    AND (
                        product_id NOT IN (SELECT id FROM products)
                        OR pack_id NOT IN (SELECT id FROM packs)
                    )
                """, (user_id,))
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"🧹 {deleted_count} آیتم نامعتبر از سبد کاربر {user_id} حذف شد")
                    self._invalidate_cache(f"cart:{user_id}")
                
                return deleted_count
        
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی سبد کاربر {user_id}: {e}")
            return 0
    
    def create_tables(self):
        """ایجاد جداول دیتابیس"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                photo_id TEXT,
                channel_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                full_name TEXT,
                phone TEXT,
                landline_phone TEXT,
                address TEXT,
                shop_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                pack_id INTEGER,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (pack_id) REFERENCES packs(id) ON DELETE CASCADE,
                UNIQUE(user_id, pack_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                items TEXT,
                total_price REAL,
                discount_amount REAL DEFAULT 0,
                final_price REAL,
                discount_code TEXT,
                status TEXT DEFAULT 'pending',
                receipt_photo TEXT,
                shipping_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                value REAL NOT NULL,
                min_purchase REAL DEFAULT 0,
                max_discount REAL,
                usage_limit INTEGER,
                used_count INTEGER DEFAULT 0,
                per_user_limit INTEGER,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discount_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                discount_code TEXT,
                order_id INTEGER,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        
        # ✅ NEW: جدول جدید برای ذخیره تخفیف‌های موقت
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS temp_discount_codes (
                user_id INTEGER PRIMARY KEY,
                discount_code TEXT NOT NULL,
                discount_amount REAL NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        self._create_indexes()
        self._migrate_existing_data()
    
    def _migrate_existing_data(self):
        """
        ✅ اضافه کردن ستون‌های جدید و migrate کردن سفارشات قدیمی
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # چک کردن وجود ستون per_user_limit
            cursor.execute("PRAGMA table_info(discount_codes)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'per_user_limit' not in columns:
                logger.info("🔄 اضافه کردن ستون per_user_limit به جدول discount_codes...")
                cursor.execute("ALTER TABLE discount_codes ADD COLUMN per_user_limit INTEGER")
                conn.commit()
                logger.info("✅ ستون per_user_limit اضافه شد")
            
            # چک کردن وجود ستون expires_at در orders
            cursor.execute("PRAGMA table_info(orders)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'expires_at' not in columns:
                logger.info("🔄 اضافه کردن ستون expires_at...")
                cursor.execute("ALTER TABLE orders ADD COLUMN expires_at TIMESTAMP")
                conn.commit()
                
                # ✅ FIX: فقط یکبار وقتی ستون اضافه میشه، migration رو اجرا کن
                # و با 1 ساعت (نه 1 روز)
                logger.info("🔄 Migration سفارشات قدیمی به 1 ساعت...")
                cursor.execute("""
                    UPDATE orders 
                    SET expires_at = datetime(created_at, '+1 hour')
                    WHERE expires_at IS NULL
                """)
                conn.commit()
                logger.info("✅ Migration سفارشات قدیمی انجام شد")
            
            logger.info("✅ بررسی migration‌ها تمام شد")
        except Exception as e:
            logger.error(f"❌ خطا در مهاجرت: {e}")
    
    def _create_indexes(self):
        """ایجاد Index ها برای بهبود سرعت"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_orders_expires_at ON orders(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_cart_user_pack ON cart(user_id, pack_id)",
            "CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code)",
            "CREATE INDEX IF NOT EXISTS idx_packs_product_id ON packs(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_temp_discount_user ON temp_discount_codes(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_discount_usage_user_code ON discount_usage(user_id, discount_code)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"⚠️ Failed to create index: {e}")
        
        conn.commit()
    
    # ==================== محصولات ====================
    
    def add_product(self, name: str, description: str, photo_id: str):
        try:
            with self.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO products (name, description, photo_id) VALUES (?, ?, ?)",
                    (name, description, photo_id)
                )
                product_id = cursor.lastrowid
                
                log_database_operation("INSERT", "products", product_id)
                self._invalidate_cache("products:")
                return product_id

        except Exception as e:
            log_error("Database", f"خطا در افزودن محصول: {e}")
            raise
    
    def get_product(self, product_id):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return cursor.fetchone()
    
    def get_all_products(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY created_at DESC")
        return cursor.fetchall()
    
    def update_product_name(self, product_id: int, name: str):
        with self.transaction() as cursor:
            cursor.execute("UPDATE products SET name = ? WHERE id = ?", (name, product_id))
        self._invalidate_cache(f"product:{product_id}")
        self._invalidate_cache("products:")
    
    def update_product_description(self, product_id: int, description: str):
        with self.transaction() as cursor:
            cursor.execute("UPDATE products SET description = ? WHERE id = ?", (description, product_id))
        self._invalidate_cache(f"product:{product_id}")
    
    def update_product_photo(self, product_id: int, photo_id: str):
        with self.transaction() as cursor:
            cursor.execute("UPDATE products SET photo_id = ? WHERE id = ?", (photo_id, product_id))
        self._invalidate_cache(f"product:{product_id}")
    
    def save_channel_message_id(self, product_id: int, message_id: int) -> bool:
        try:
            with self.transaction() as cursor:
                cursor.execute("UPDATE products SET channel_message_id = ? WHERE id = ?", (message_id, product_id))
            
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT channel_message_id FROM products WHERE id = ?", (product_id,))
            saved_id = cursor.fetchone()
            
            if saved_id and saved_id[0] == message_id:
                logger.info(f"✅ channel_message_id={message_id} ذخیره شد برای product={product_id}")
                return True
            else:
                logger.error(f"❌ خطا در ذخیره channel_message_id")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در save_channel_message_id: {e}")
            return False
    
    def delete_product(self, product_id: int):
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
            cursor.execute("DELETE FROM packs WHERE product_id = ?", (product_id,))
            cursor.execute("DELETE FROM cart WHERE product_id = ?", (product_id,))
        
        self._invalidate_cache(f"product:{product_id}")
        self._invalidate_cache(f"packs:{product_id}")
        self._invalidate_cache("products:")
    
    # ==================== پک‌ها ====================
    
    def add_pack(self, product_id: int, name: str, quantity: int, price: float):
        with self.transaction() as cursor:
            cursor.execute("INSERT INTO packs (product_id, name, quantity, price) VALUES (?, ?, ?, ?)", 
                         (product_id, name, quantity, price))
            pack_id = cursor.lastrowid
        
        self._invalidate_cache(f"packs:{product_id}")
        return pack_id
    
    def get_packs(self, product_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packs WHERE product_id = ?", (product_id,))
        return cursor.fetchall()
    
    def get_pack(self, pack_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packs WHERE id = ?", (pack_id,))
        return cursor.fetchone()
    
    def update_pack(self, pack_id: int, name: str, quantity: int, price: float):
        pack = self.get_pack(pack_id)
        if pack:
            product_id = pack[1]
            with self.transaction() as cursor:
                cursor.execute("UPDATE packs SET name = ?, quantity = ?, price = ? WHERE id = ?", 
                             (name, quantity, price, pack_id))
            self._invalidate_cache(f"packs:{product_id}")
    
    def delete_pack(self, pack_id: int):
        pack = self.get_pack(pack_id)
        if pack:
            product_id = pack[1]
            with self.transaction() as cursor:
                cursor.execute("DELETE FROM packs WHERE id = ?", (pack_id,))
                cursor.execute("DELETE FROM cart WHERE pack_id = ?", (pack_id,))
            
            self._invalidate_cache(f"packs:{product_id}")
    
    # ==================== کاربران ====================
    
    def add_user(self, user_id: int, username: Optional[str], first_name: str):
        with self.transaction() as cursor:
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", 
                         (user_id, username, first_name))
    
    def update_user_info(self, user_id: int, phone=None, landline_phone=None, address=None, full_name=None, shop_name=None):
        """
        ✅ FIXED: بروزرسانی یکجا برای جلوگیری از race condition
        """
        updates = []
        params = []
        
        if phone is not None:
            updates.append("phone = ?")
            params.append(self._sanitize_text_input(phone, 20))
        if landline_phone is not None:
            updates.append("landline_phone = ?")
            params.append(self._sanitize_text_input(landline_phone, 20))
        if address is not None:
            updates.append("address = ?")
            params.append(self._sanitize_text_input(address, 500))
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(self._sanitize_text_input(full_name, 100))
        if shop_name is not None:
            updates.append("shop_name = ?")
            params.append(self._sanitize_text_input(shop_name, 100))
        
        if not updates:
            return
        
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
        
        with self.transaction() as cursor:
            cursor.execute(query, params)
        
        self._invalidate_cache(f"user:{user_id}")
    
    def get_user(self, user_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    def get_all_users(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
    
    # ==================== سبد خرید ====================
    
    def add_to_cart(self, user_id: int, product_id: int, pack_id: int, quantity: int = 1):
        """
        ✅ FIXED: استفاده از INSERT ... ON CONFLICT
        """
        try:
            pack = self.get_pack(pack_id)
            if not pack:
                logger.warning(f"⚠️ Pack {pack_id} not found")
                return
            
            pack_quantity = pack[3]
            actual_quantity = quantity * pack_quantity
            
            with self.transaction() as cursor:
                cursor.execute("""
                    INSERT INTO cart (user_id, product_id, pack_id, quantity) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, pack_id) DO UPDATE 
                    SET quantity = quantity + excluded.quantity
                """, (user_id, product_id, pack_id, actual_quantity))
            
            self._invalidate_cache(f"cart:{user_id}")
            logger.info(f"✅ Cart updated: user={user_id}, pack={pack_id}, qty={actual_quantity}")
            
        except Exception as e:
            logger.error(f"❌ Cart error: {e}")
            raise
    
    def get_cart(self, user_id: int):
        """✅ FIXED: حذف clean_invalid_cart_items"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, p.name, pk.name, pk.quantity, pk.price, c.quantity
            FROM cart c
            JOIN products p ON c.product_id = p.id
            JOIN packs pk ON c.pack_id = pk.id
            WHERE c.user_id = ?
        """, (user_id,))
        return cursor.fetchall()
    
    def clear_cart(self, user_id: int):
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        self._invalidate_cache(f"cart:{user_id}")
    
    def remove_from_cart(self, cart_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM cart WHERE id = ?", (cart_id,))
        result = cursor.fetchone()
        
        cursor.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        conn.commit()
        
        if result:
            self._invalidate_cache(f"cart:{result[0]}")
    
    # ==================== سفارشات ====================
    
    def create_order(self, user_id: int, items: List[dict], total_price: float, 
                    discount_amount: float = 0, final_price: Optional[float] = None, 
                    discount_code: Optional[str] = None):
        """ایجاد سفارش با تاریخ انقضا ۱ ساعته (با timezone تهران)"""
        items_json = json.dumps(items, ensure_ascii=False)
        if final_price is None:
            final_price = total_price - discount_amount
        
        # ✅ FIX: استفاده از زمان تهران
        now_tehran = get_tehran_now()
        expires_at = now_tehran + timedelta(hours=1)  # ۱ ساعت
        
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT INTO orders 
                (user_id, items, total_price, discount_amount, final_price, discount_code, expires_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, items_json, total_price, discount_amount, final_price, discount_code, expires_at))
            order_id = cursor.lastrowid
            
        self._invalidate_cache("stats:")
        return order_id
    
    def get_order(self, order_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return cursor.fetchone()
    
    def update_order_status(self, order_id: int, status: str):
        with self.transaction() as cursor:
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        self._invalidate_cache("stats:")
    
    def add_receipt(self, order_id: int, photo_id: str):
        with self.transaction() as cursor:
            cursor.execute("UPDATE orders SET receipt_photo = ?, status = 'receipt_sent' WHERE id = ?", 
                         (photo_id, order_id))
    
    def update_shipping_method(self, order_id: int, method: str):
        with self.transaction() as cursor:
            cursor.execute("UPDATE orders SET shipping_method = ? WHERE id = ?", (method, order_id))
    
    def get_pending_orders(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC")
        return cursor.fetchall()
    
    def get_waiting_payment_orders(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE status = 'waiting_payment' ORDER BY created_at DESC")
        return cursor.fetchall()
    
    def get_user_orders(self, user_id: int):
        """دریافت سفارشات کاربر"""
        conn = self._get_conn()
        cursor = conn.cursor()
    
        cursor.execute("""
            SELECT * FROM orders 
            WHERE user_id = ? 
            AND status != 'rejected'
            AND (
                status IN ('payment_confirmed', 'confirmed')
                OR datetime(expires_at) > datetime('now')
            )
            ORDER BY created_at DESC
        """, (user_id,))
    
        return cursor.fetchall()
    
    def delete_order(self, order_id: int):
        """حذف سفارش"""
        try:
            with self.transaction() as cursor:
                cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
                log_database_operation("DELETE", "orders", order_id)
                self._invalidate_cache("stats:")
                return True
        except Exception as e:
            logger.error(f"❌ خطا در حذف سفارش {order_id}: {e}")
            return False
    
    def is_order_expired(self, order_id: int) -> bool:
        """بررسی منقضی بودن سفارش (با timezone تهران)"""
        order = self.get_order(order_id)
        if not order:
            return True
        
        expires_at = order[11]
        if not expires_at:
            return False
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        # ✅ FIX: مقایسه با زمان تهران
        # اگر expires_at بدون timezone هست، timezone تهران بهش اضافه می‌کنیم
        if expires_at.tzinfo is None:
            expires_at = TEHRAN_TZ.localize(expires_at)
        
        return get_tehran_now() > expires_at
    
    def cleanup_old_orders(self, days_old: int = 7) -> dict:
        """پاکسازی سفارشات قدیمی (با timezone تهران)"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # ✅ FIX: استفاده از زمان تهران
            cutoff_date = get_tehran_now() - timedelta(days=days_old)
            
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE (
                    status = 'rejected' 
                    OR (datetime(expires_at) < datetime('now') AND status NOT IN ('payment_confirmed', 'confirmed'))
                )
                AND datetime(created_at) < datetime(?)
            """, (cutoff_date,))
            
            count_before = cursor.fetchone()[0]
            
            cursor.execute("""
                DELETE FROM orders 
                WHERE (
                    status = 'rejected' 
                    OR (datetime(expires_at) < datetime('now') AND status NOT IN ('payment_confirmed', 'confirmed'))
                )
                AND datetime(created_at) < datetime(?)
            """, (cutoff_date,))
            
            conn.commit()
            deleted_count = cursor.rowcount
            
            logger.info(f"🧹 پاکسازی: {deleted_count} سفارش قدیمی حذف شد")
            
            report = {
                'deleted_count': deleted_count,
                'days_old': days_old,
                'cutoff_date': cutoff_date.isoformat(),
                'success': True
            }
            
            self._invalidate_cache("stats:")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی سفارشات: {e}")
            return {
                'deleted_count': 0,
                'success': False,
                'error': str(e)
            }
    
    # ==================== تخفیف ====================
    
    def create_discount(self, code: str, type: str, value: float, min_purchase: float = 0, 
                       max_discount: Optional[float] = None, usage_limit: Optional[int] = None,
                       per_user_limit: Optional[int] = None,
                       start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        ایجاد کد تخفیف جدید
        
        Args:
            code: کد تخفیف
            type: نوع تخفیف (percentage یا fixed)
            value: مقدار تخفیف
            min_purchase: حداقل خرید
            max_discount: حداکثر تخفیف (برای درصدی)
            usage_limit: محدودیت کل استفاده
            per_user_limit: محدودیت استفاده به ازای هر کاربر
            start_date: تاریخ شروع
            end_date: تاریخ پایان
        """
        with self.transaction() as cursor:
            cursor.execute("""
                INSERT INTO discount_codes 
                (code, type, value, min_purchase, max_discount, usage_limit, per_user_limit, start_date, end_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, type, value, min_purchase, max_discount, usage_limit, per_user_limit, start_date, end_date))
            discount_id = cursor.lastrowid
        return discount_id
    
    def get_discount(self, code: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discount_codes WHERE code = ? AND is_active = 1", (code,))
        return cursor.fetchone()
    
    def get_all_discounts(self):
        """دریافت تمام کدهای تخفیف"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discount_codes ORDER BY created_at DESC")
        return cursor.fetchall()
    
    def get_user_discount_usage_count(self, user_id: int, discount_code: str) -> int:
        """
        ✅ NEW: دریافت تعداد دفعات استفاده کاربر از یک کد تخفیف
        
        Args:
            user_id: شناسه کاربر
            discount_code: کد تخفیف
            
        Returns:
            تعداد دفعات استفاده
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM discount_usage 
                WHERE user_id = ? AND discount_code = ?
            """, (user_id, discount_code))
            
            result = cursor.fetchone()
            return result[0] if result else 0
        
        except Exception as e:
            logger.error(f"❌ خطا در دریافت تعداد استفاده کاربر {user_id} از کد {discount_code}: {e}")
            return 0
    
    def use_discount(self, user_id: int, discount_code: str, order_id: int):
        with self.transaction() as cursor:
            cursor.execute("INSERT INTO discount_usage (user_id, discount_code, order_id) VALUES (?, ?, ?)", 
                         (user_id, discount_code, order_id))
            cursor.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?", (discount_code,))
    
    def toggle_discount(self, discount_id: int):
        with self.transaction() as cursor:
            cursor.execute("UPDATE discount_codes SET is_active = 1 - is_active WHERE id = ?", (discount_id,))
    
    def delete_discount(self, discount_id: int):
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM discount_codes WHERE id = ?", (discount_id,))
    
    # ==================== ✅ NEW: تخفیف‌های موقت ====================
    
    def save_temp_discount(self, user_id: int, discount_code: str, discount_amount: float):
        """
        ذخیره کد تخفیف موقت برای کاربر (با timezone تهران)
        """
        # ✅ FIX: استفاده از زمان تهران
        expires_at = get_tehran_now() + timedelta(hours=1)
        
        try:
            with self.transaction() as cursor:
                cursor.execute("""
                    INSERT INTO temp_discount_codes (user_id, discount_code, discount_amount, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        discount_code = excluded.discount_code,
                        discount_amount = excluded.discount_amount,
                        applied_at = CURRENT_TIMESTAMP,
                        expires_at = excluded.expires_at
                """, (user_id, discount_code, discount_amount, expires_at))
            
            logger.info(f"✅ Temp discount saved for user {user_id}: {discount_code}")
        
        except Exception as e:
            logger.error(f"❌ Error saving temp discount: {e}")
    
    def get_temp_discount(self, user_id: int) -> Optional[dict]:
        """
        دریافت کد تخفیف موقت کاربر
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT discount_code, discount_amount, expires_at
                FROM temp_discount_codes
                WHERE user_id = ? AND datetime(expires_at) > datetime('now')
            """, (user_id,))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    'code': result[0],
                    'amount': result[1],
                    'expires_at': result[2]
                }
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Error getting temp discount: {e}")
            return None
    
    def clear_temp_discount(self, user_id: int):
        """پاک کردن تخفیف موقت بعد از استفاده"""
        try:
            with self.transaction() as cursor:
                cursor.execute("DELETE FROM temp_discount_codes WHERE user_id = ?", (user_id,))
            
            logger.info(f"✅ Temp discount cleared for user {user_id}")
        
        except Exception as e:
            logger.error(f"❌ Error clearing temp discount: {e}")
    
    def cleanup_expired_temp_discounts(self):
        """پاکسازی تخفیف‌های موقت منقضی شده"""
        try:
            with self.transaction() as cursor:
                cursor.execute("""
                    DELETE FROM temp_discount_codes
                    WHERE datetime(expires_at) < datetime('now')
                """)
                
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logger.info(f"🧹 {deleted_count} expired temp discounts cleaned up")
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"❌ Error cleaning up temp discounts: {e}")
            return 0
    
    # ==================== آمار ====================
    
    def get_statistics(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM orders")
        stats['total_orders'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')")
        stats['today_orders'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) >= DATE('now', '-7 days')")
        stats['week_orders'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('confirmed', 'payment_confirmed')")
        total_income = cursor.fetchone()[0]
        stats['total_income'] = total_income if total_income else 0
        
        cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('confirmed', 'payment_confirmed') AND DATE(created_at) = DATE('now')")
        today_income = cursor.fetchone()[0]
        stats['today_income'] = today_income if today_income else 0
        
        cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('confirmed', 'payment_confirmed') AND DATE(created_at) >= DATE('now', '-7 days')")
        week_income = cursor.fetchone()[0]
        stats['week_income'] = week_income if week_income else 0
        
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) >= DATE('now', '-7 days')")
        stats['week_new_users'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        stats['total_products'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        stats['pending_orders'] = cursor.fetchone()[0]
        
        cursor.execute("""SELECT items FROM orders WHERE status IN ('confirmed', 'payment_confirmed')""")
        product_counts = {}
        for row in cursor.fetchall():
            items = json.loads(row[0])
            for item in items:
                product_name = item.get('product', '')
                product_counts[product_name] = product_counts.get(product_name, 0) + item.get('quantity', 0)
        
        if product_counts:
            stats['most_popular'] = max(product_counts.items(), key=lambda x: x[1])[0]
        else:
            stats['most_popular'] = "هنوز داده‌ای نیست"
        
        return stats
    
    @property
    def cursor(self):
        """برای backward compatibility"""
        return self._get_conn().cursor()
    
    @property  
    def conn(self):
        """برای backward compatibility"""
        return self._get_conn()
    
    def close(self):
        try:
            if hasattr(self, 'pool') and self.pool:
                self.pool.cleanup_all()
            logger.info("✅ Database connections closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing database: {e}")
