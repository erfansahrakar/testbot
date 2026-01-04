"""
مدیریت دیتابیس با SQLite
🔒 نسخه بهبود یافته با امنیت بالا
✅ Transaction Management + Connection Pool + Error Handling
🔴 جایگزین database.py قبلی می‌شود
"""
import sqlite3
import json
import threading
from logger import log_database_operation, log_error
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager
from config import DATABASE_NAME
import logging

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """مدیریت Connection Pool برای دیتابیس"""
    
    def __init__(self, database_name: str):
        self.database_name = database_name
        self._local = threading.local()
        self._lock = threading.Lock()
        
    def get_connection(self) -> sqlite3.Connection:
        """دریافت connection برای thread فعلی"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            try:
                conn = sqlite3.connect(
                    self.database_name,
                    timeout=30.0,
                    isolation_level=None
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                self._local.connection = conn
                logger.debug(f"Connection created for thread {threading.current_thread().name}")
            except sqlite3.Error as e:
                logger.error(f"Failed to create connection: {e}")
                raise
        
        return self._local.connection
    
    def close_connection(self):
        """بستن connection thread فعلی"""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            try:
                self._local.connection.close()
                logger.debug(f"Connection closed for thread {threading.current_thread().name}")
            except sqlite3.Error as e:
                logger.error(f"Failed to close connection: {e}")
            finally:
                self._local.connection = None


class DatabaseError(Exception):
    """خطای عملیات دیتابیس"""
    pass


class Database:
    """کلاس مدیریت دیتابیس با امنیت بالا"""

    def clean_invalid_cart_items(self, user_id: int):
        """
        حذف آیتم‌های نامعتبر از سبد
        (محصولات یا پک‌هایی که حذف شدن)
    
        ⚠️ این تابع رو قبل از get_cart صدا بزن تا از ارور جلوگیری بشه
        """
        try:
            self.cursor.execute("""
                DELETE FROM cart 
                WHERE user_id = ? 
                AND (
                    product_id NOT IN (SELECT id FROM products)
                    OR pack_id NOT IN (SELECT id FROM packs)
                )
            """, (user_id,))
            self.conn.commit()
        
            deleted_count = self.cursor.rowcount
            if deleted_count > 0:
                logger.info(f"🧹 {deleted_count} آیتم نامعتبر از سبد کاربر {user_id} حذف شد")
        
            return deleted_count
        
        except Exception as e:
            logger.error(f"خطا در پاکسازی سبد کاربر {user_id}: {e}")
            return 0
        
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.pool = DatabaseConnectionPool(DATABASE_NAME)
        self.create_tables()
    
    def _get_conn(self) -> sqlite3.Connection:
        """دریافت connection"""
        return self.pool.get_connection()
    
    @contextmanager
    def transaction(self):
        """Context Manager برای تراکنش‌های دیتابیس"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN")
            yield cursor
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.error(f"IntegrityError: {e}")
            raise DatabaseError(f"خطای یکپارچگی داده: {e}")
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"OperationalError: {e}")
            raise DatabaseError(f"خطای عملیاتی: {e}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise DatabaseError(f"خطای تراکنش: {e}")
    
    def create_tables(self):
        """ایجاد جداول دیتابیس"""
        
        # جدول محصولات
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                photo_id TEXT,
                channel_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول پک‌ها
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        
        # جدول کاربران
        self.cursor.execute("""
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
        
        # جدول سبد خرید
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                pack_id INTEGER,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (pack_id) REFERENCES packs(id)
            )
        """)
        
        # جدول سفارشات
        self.cursor.execute("""
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
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # جدول کد تخفیف
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                value REAL NOT NULL,
                min_purchase REAL DEFAULT 0,
                max_discount REAL,
                usage_limit INTEGER,
                used_count INTEGER DEFAULT 0,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول استفاده از کد تخفیف
        self.cursor.execute("""
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
        
        self.conn.commit()
        self._create_indexes()
    
    def _create_indexes(self):
        """ایجاد Index ها برای بهبود سرعت"""
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code)",
            "CREATE INDEX IF NOT EXISTS idx_packs_product_id ON packs(product_id)",
        ]
        
        for index_sql in indexes:
            try:
                self.cursor.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"Failed to create index: {e}")
        
        self.conn.commit()
    
    # ==================== محصولات ====================
    
    def add_product(self, name: str, description: str, photo_id: str):
        try:
            self.cursor.execute(
                "INSERT INTO products (name, description, photo_id) VALUES (?, ?, ?)",
                (name, description, photo_id)
            )
            self.conn.commit()

            product_id = self.cursor.lastrowid

            # 🆕 لاگ عملیات
            log_database_operation("INSERT", "products", product_id)

            return product_id

        except Exception as e:
            log_error("Database", f"خطا در افزودن محصول: {e}")
            raise
    
    def get_product(self, product_id):
        """دریافت اطلاعات یک محصول"""
        self.cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return self.cursor.fetchone()
    
    def get_all_products(self):
        """دریافت تمام محصولات"""
        self.cursor.execute("SELECT * FROM products ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def update_product_name(self, product_id: int, name: str):
        """ویرایش نام محصول"""
        self.cursor.execute(
            "UPDATE products SET name = ? WHERE id = ?",
            (name, product_id)
        )
        self.conn.commit()
    
    def update_product_description(self, product_id: int, description: str):
        """ویرایش توضیحات محصول"""
        self.cursor.execute(
            "UPDATE products SET description = ? WHERE id = ?",
            (description, product_id)
        )
        self.conn.commit()
    
    def update_product_photo(self, product_id: int, photo_id: str):
        """ویرایش عکس محصول"""
        self.cursor.execute(
            "UPDATE products SET photo_id = ? WHERE id = ?",
            (photo_id, product_id)
        )
        self.conn.commit()
    
    def save_channel_message_id(self, product_id: int, message_id: int) -> bool:
        """ذخیره شناسه پیام کانال"""
        try:
            self.cursor.execute(
                "UPDATE products SET channel_message_id = ? WHERE id = ?",
                (message_id, product_id)
            )
            self.conn.commit()
            
            # تایید ذخیره
            self.cursor.execute("SELECT channel_message_id FROM products WHERE id = ?", (product_id,))
            saved_id = self.cursor.fetchone()
            if saved_id and saved_id[0] == message_id:
                print(f"✅ باگ 1 FIX: channel_message_id={message_id} ذخیره شد برای product={product_id}")
                return True
            else:
                print(f"❌ باگ 1: خطا در ذخیره channel_message_id")
                return False
        except Exception as e:
            print(f"❌ باگ 1: خطا در save_channel_message_id: {e}")
            return False
    
    def delete_product(self, product_id: int):
        """حذف محصول"""
        self.cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.cursor.execute("DELETE FROM packs WHERE product_id = ?", (product_id,))
        self.conn.commit()
    
    # ==================== پک‌ها ====================
    
    def add_pack(self, product_id: int, name: str, quantity: int, price: float):
        """افزودن پک به محصول"""
        self.cursor.execute(
            "INSERT INTO packs (product_id, name, quantity, price) VALUES (?, ?, ?, ?)",
            (product_id, name, quantity, price)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_packs(self, product_id: int):
        """دریافت پک‌های یک محصول"""
        self.cursor.execute("SELECT * FROM packs WHERE product_id = ?", (product_id,))
        return self.cursor.fetchall()
    
    def get_pack(self, pack_id: int):
        """دریافت اطلاعات یک پک"""
        self.cursor.execute("SELECT * FROM packs WHERE id = ?", (pack_id,))
        return self.cursor.fetchone()
    
    def update_pack(self, pack_id: int, name: str, quantity: int, price: float):
        """ویرایش پک"""
        self.cursor.execute(
            "UPDATE packs SET name = ?, quantity = ?, price = ? WHERE id = ?",
            (name, quantity, price, pack_id)
        )
        self.conn.commit()
    
    def delete_pack(self, pack_id: int):
        """حذف پک"""
        self.cursor.execute("DELETE FROM packs WHERE id = ?", (pack_id,))
        self.conn.commit()
    
    # ==================== کاربران ====================
    
    def add_user(self, user_id: int, username: Optional[str], first_name: str):
        """افزودن کاربر جدید"""
        self.cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        self.conn.commit()
    
    def update_user_info(self, user_id: int, phone=None, landline_phone=None, address=None, full_name=None, shop_name=None):
        """بروزرسانی اطلاعات کاربر"""
        if phone:
            self.cursor.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
        if landline_phone:
            self.cursor.execute("UPDATE users SET landline_phone = ? WHERE user_id = ?", (landline_phone, user_id))
        if address:
            self.cursor.execute("UPDATE users SET address = ? WHERE user_id = ?", (address, user_id))
        if full_name:
            self.cursor.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (full_name, user_id))
        if shop_name:
            self.cursor.execute("UPDATE users SET shop_name = ? WHERE user_id = ?", (shop_name, user_id))
        self.conn.commit()
    
    def get_user(self, user_id: int):
        """دریافت اطلاعات کاربر"""
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def get_all_users(self):
        """دریافت همه کاربران"""
        self.cursor.execute("SELECT * FROM users")
        return self.cursor.fetchall()
        
        # ==================== سبد خرید ====================
    
    def add_to_cart(self, user_id: int, product_id: int, pack_id: int, quantity: int = 1):
        """افزودن به سبد خرید"""
        self.cursor.execute(
            "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ? AND pack_id = ?",
            (user_id, product_id, pack_id)
        )
        existing = self.cursor.fetchone()
        
        pack = self.get_pack(pack_id)
        if not pack:
            return
        
        pack_quantity = pack[3]
        actual_quantity = quantity * pack_quantity
        
        if existing:
            new_quantity = existing[1] + actual_quantity
            self.cursor.execute(
                "UPDATE cart SET quantity = ? WHERE id = ?",
                (new_quantity, existing[0])
            )
        else:
            self.cursor.execute(
                "INSERT INTO cart (user_id, product_id, pack_id, quantity) VALUES (?, ?, ?, ?)",
                (user_id, product_id, pack_id, actual_quantity)
            )
        self.conn.commit()

    
    def get_cart(self, user_id: int):
    """دریافت سبد خرید - با پاکسازی خودکار"""
    # ✅ اول آیتم‌های نامعتبر رو حذف کن
    self.clean_invalid_cart_items(user_id)
    
    # بعد سبد رو برگردون
    self.cursor.execute("""
        SELECT c.id, p.name, pk.name, pk.quantity, pk.price, c.quantity
        FROM cart c
        JOIN products p ON c.product_id = p.id
        JOIN packs pk ON c.pack_id = pk.id
        WHERE c.user_id = ?
    """, (user_id,))
    return self.cursor.fetchall()
    
    def clear_cart(self, user_id: int):
        """خالی کردن سبد خرید"""
        self.cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    def remove_from_cart(self, cart_id: int):
        """حذف آیتم از سبد"""
        self.cursor.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        self.conn.commit()
    
    # ==================== سفارشات ====================
    
    def create_order(self, user_id: int, items: List[dict], total_price: float, 
                    discount_amount: float = 0, final_price: Optional[float] = None, 
                    discount_code: Optional[str] = None):
        """ایجاد سفارش جدید"""
        items_json = json.dumps(items, ensure_ascii=False)
        if final_price is None:
            final_price = total_price - discount_amount
        
        self.cursor.execute(
            "INSERT INTO orders (user_id, items, total_price, discount_amount, final_price, discount_code) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, items_json, total_price, discount_amount, final_price, discount_code)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_order(self, order_id: int):
        """دریافت اطلاعات سفارش"""
        self.cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return self.cursor.fetchone()
    
    def update_order_status(self, order_id: int, status: str):
        """بروزرسانی وضعیت سفارش"""
        self.cursor.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id)
        )
        self.conn.commit()
    
    def add_receipt(self, order_id: int, photo_id: str):
        """افزودن رسید به سفارش"""
        self.cursor.execute(
            "UPDATE orders SET receipt_photo = ?, status = 'receipt_sent' WHERE id = ?",
            (photo_id, order_id)
        )
        self.conn.commit()
    
    def update_shipping_method(self, order_id: int, method: str):
        """بروزرسانی نحوه ارسال"""
        self.cursor.execute(
            "UPDATE orders SET shipping_method = ? WHERE id = ?",
            (method, order_id)
        )
        self.conn.commit()
    
    def get_pending_orders(self):
        """دریافت سفارشات در انتظار تایید"""
        self.cursor.execute("SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def get_waiting_payment_orders(self):
        """دریافت سفارشات در انتظار پرداخت"""
        self.cursor.execute("SELECT * FROM orders WHERE status = 'waiting_payment' ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def get_user_orders(self, user_id: int):
        """دریافت سفارشات یک کاربر"""
        self.cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return self.cursor.fetchall()
    
    # ==================== تخفیف ====================
    
    def create_discount(self, code: str, type: str, value: float, min_purchase: float = 0, 
                       max_discount: Optional[float] = None, usage_limit: Optional[int] = None, 
                       start_date: Optional[str] = None, end_date: Optional[str] = None):
        """ایجاد کد تخفیف"""
        self.cursor.execute(
            "INSERT INTO discount_codes (code, type, value, min_purchase, max_discount, usage_limit, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (code, type, value, min_purchase, max_discount, usage_limit, start_date, end_date)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_discount(self, code: str):
        """دریافت اطلاعات کد تخفیف"""
        self.cursor.execute("SELECT * FROM discount_codes WHERE code = ? AND is_active = 1", (code,))
        return self.cursor.fetchone()
    
    def get_all_discounts(self):
        """دریافت همه کدهای تخفیف"""
        self.cursor.execute("SELECT * FROM discount_codes ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def use_discount(self, user_id: int, discount_code: str, order_id: int):
        """ثبت استفاده از کد تخفیف"""
        self.cursor.execute(
            "INSERT INTO discount_usage (user_id, discount_code, order_id) VALUES (?, ?, ?)",
            (user_id, discount_code, order_id)
        )
        self.cursor.execute(
            "UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?",
            (discount_code,)
        )
        self.conn.commit()
    
    def toggle_discount(self, discount_id: int):
        """فعال/غیرفعال کردن کد تخفیف"""
        self.cursor.execute(
            "UPDATE discount_codes SET is_active = 1 - is_active WHERE id = ?",
            (discount_id,)
        )
        self.conn.commit()
    
    def delete_discount(self, discount_id: int):
        """حذف کد تخفیف"""
        self.cursor.execute("DELETE FROM discount_codes WHERE id = ?", (discount_id,))
        self.conn.commit()
    
    # ==================== آمار ====================
    
    def get_statistics(self):
        """دریافت آمار کلی"""
        stats = {}
        
        # تعداد کل سفارشات
        self.cursor.execute("SELECT COUNT(*) FROM orders")
        stats['total_orders'] = self.cursor.fetchone()[0]
        
        # تعداد سفارشات امروز
        self.cursor.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')")
        stats['today_orders'] = self.cursor.fetchone()[0]
        
        # تعداد سفارشات این هفته
        self.cursor.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) >= DATE('now', '-7 days')")
        stats['week_orders'] = self.cursor.fetchone()[0]
        
        # درآمد کل (فقط سفارشات تایید شده)
        self.cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('confirmed', 'payment_confirmed')")
        total_income = self.cursor.fetchone()[0]
        stats['total_income'] = total_income if total_income else 0
        
        # درآمد امروز
        self.cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('confirmed', 'payment_confirmed') AND DATE(created_at) = DATE('now')")
        today_income = self.cursor.fetchone()[0]
        stats['today_income'] = today_income if today_income else 0
        
        # درآمد این هفته
        self.cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('confirmed', 'payment_confirmed') AND DATE(created_at) >= DATE('now', '-7 days')")
        week_income = self.cursor.fetchone()[0]
        stats['week_income'] = week_income if week_income else 0
        
        # تعداد کاربران
        self.cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = self.cursor.fetchone()[0]
        
        # کاربران جدید این هفته
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) >= DATE('now', '-7 days')")
        stats['week_new_users'] = self.cursor.fetchone()[0]
        
        # تعداد محصولات
        self.cursor.execute("SELECT COUNT(*) FROM products")
        stats['total_products'] = self.cursor.fetchone()[0]
        
        # تعداد سفارشات در انتظار
        self.cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        stats['pending_orders'] = self.cursor.fetchone()[0]
        
        # محبوب‌ترین محصول
        self.cursor.execute("""
            SELECT items FROM orders 
            WHERE status IN ('confirmed', 'payment_confirmed')
        """)
        product_counts = {}
        for row in self.cursor.fetchall():
            items = json.loads(row[0])
            for item in items:
                product_name = item.get('product', '')
                product_counts[product_name] = product_counts.get(product_name, 0) + item.get('quantity', 0)
        
        if product_counts:
            stats['most_popular'] = max(product_counts.items(), key=lambda x: x[1])[0]
        else:
            stats['most_popular'] = "هنوز داده‌ای نیست"
        
        return stats
    
    def close(self):
        """بستن اتصال"""
        self.conn.close()
        self.pool.close_connection()
