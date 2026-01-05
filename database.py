"""
🚀 مدیریت دیتابیس با SQLite - نسخه FIX شده
✅ FIX: خطای 'no such column: c.added_at' برطرف شد
✅ Query Optimization با Indexes پیشرفته
✅ Batch Operations برای عملیات دسته‌جمعی
✅ Connection Pooling بهبود یافته
✅ Transaction Management حرفه‌ای
✅ Query Result Caching
✅ Prepared Statements
"""
import sqlite3
import json
import threading
import atexit
from logger import log_database_operation, log_error
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from contextlib import contextmanager
from config import DATABASE_NAME
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """مدیریت Connection Pool با بهینه‌سازی"""
    
    def __init__(self, database_name: str, max_connections: int = 5):
        self.database_name = database_name
        self.max_connections = max_connections
        self._local = threading.local()
        self._lock = threading.Lock()
        self._active_connections = []
        self._connection_stats = {'created': 0, 'reused': 0, 'closed': 0}
        
        atexit.register(self.cleanup_all)
        
    def get_connection(self) -> sqlite3.Connection:
        """دریافت connection با optimization"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            try:
                conn = sqlite3.connect(
                    self.database_name,
                    timeout=30.0,
                    isolation_level=None,  # Autocommit mode
                    check_same_thread=False,
                    cached_statements=100  # Cache prepared statements
                )
                conn.row_factory = sqlite3.Row
                
                # Performance optimizations
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
                conn.execute("PRAGMA synchronous = NORMAL")  # Faster writes
                conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
                conn.execute("PRAGMA temp_store = MEMORY")  # Temp tables in memory
                conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
                
                self._local.connection = conn
                
                with self._lock:
                    self._active_connections.append(conn)
                    self._connection_stats['created'] += 1
                
                logger.debug(f"✅ New connection created (total: {len(self._active_connections)})")
            except sqlite3.Error as e:
                logger.error(f"❌ Failed to create connection: {e}")
                raise
        else:
            self._connection_stats['reused'] += 1
        
        return self._local.connection
    
    def close_connection(self):
        """بستن connection thread فعلی"""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            try:
                self._local.connection.close()
                
                with self._lock:
                    if self._local.connection in self._active_connections:
                        self._active_connections.remove(self._local.connection)
                    self._connection_stats['closed'] += 1
                
                logger.debug(f"✅ Connection closed (active: {len(self._active_connections)})")
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
        
        logger.info(f"✅ All connections cleaned up. Stats: {self._connection_stats}")
    
    def get_stats(self) -> Dict[str, int]:
        """دریافت آمار connection pool"""
        return {
            **self._connection_stats,
            'active_connections': len(self._active_connections)
        }


class DatabaseError(Exception):
    """خطای عملیات دیتابیس"""
    pass


class Database:
    """کلاس مدیریت دیتابیس با Performance Optimization"""

    def __init__(self, cache_manager=None):
        """بروزرسانی شده با بهینه‌سازی کامل"""
        self.pool = DatabaseConnectionPool(DATABASE_NAME)
        self.conn = self.pool.get_connection()
        self.cursor = self.conn.cursor()
        self.cache_manager = cache_manager
        
        # Query cache برای queries پرتکرار
        self._query_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        self.create_tables()
        self._create_advanced_indexes()
        self._analyze_database()
        
        logger.info("✅ Database initialized with optimizations")
    
    def _get_conn(self) -> sqlite3.Connection:
        """دریافت connection"""
        return self.pool.get_connection()
    
    @contextmanager
    def transaction(self, immediate: bool = False):
        """Context Manager برای تراکنش‌های دیتابیس با optimization"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # IMMEDIATE برای write operations
            if immediate:
                cursor.execute("BEGIN IMMEDIATE")
            else:
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
        
        # پاک کردن query cache مرتبط
        keys_to_remove = [k for k in self._query_cache.keys() if pattern in k]
        for key in keys_to_remove:
            self._query_cache.pop(key, None)
    
    def _get_cached_query(self, cache_key: str, query: str, params: tuple = ()) -> Optional[List]:
        """اجرای query با caching"""
        if cache_key in self._query_cache:
            self._cache_hits += 1
            logger.debug(f"📦 Query cache HIT: {cache_key}")
            return self._query_cache[cache_key]
        
        self._cache_misses += 1
        self.cursor.execute(query, params)
        result = self.cursor.fetchall()
        
        # Cache کردن نتیجه
        self._query_cache[cache_key] = result
        
        # محدود کردن سایز cache
        if len(self._query_cache) > 100:
            # حذف قدیمی‌ترین item
            self._query_cache.pop(next(iter(self._query_cache)))
        
        return result
    
    def clean_invalid_cart_items(self, user_id: int) -> int:
        """Batch operation: حذف آیتم‌های نامعتبر از سبد"""
        try:
            with self.transaction(immediate=True) as cursor:
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
        """✅ FIX: ایجاد جداول دیتابیس - اصلاح شده"""
        
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
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)
        
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ✅ FIX: جدول cart با نام صحیح ستون
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                pack_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (pack_id) REFERENCES packs(id) ON DELETE CASCADE
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items TEXT NOT NULL,
                total_price REAL NOT NULL,
                discount_amount REAL DEFAULT 0,
                final_price REAL NOT NULL,
                discount_code TEXT,
                status TEXT DEFAULT 'pending',
                receipt_photo TEXT,
                shipping_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
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
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS discount_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                discount_code TEXT NOT NULL,
                order_id INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        
        self.conn.commit()
        logger.info("✅ All tables created successfully")
    
    def _create_advanced_indexes(self):
        """ایجاد Indexes پیشرفته برای بهبود Performance"""
        
        indexes = [
            # Orders indexes
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status)",
            
            # ✅ FIX: Cart indexes با نام صحیح ستون
            "CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_cart_product_pack ON cart(product_id, pack_id)",
            "CREATE INDEX IF NOT EXISTS idx_cart_user_product ON cart(user_id, product_id, pack_id)",
            "CREATE INDEX IF NOT EXISTS idx_cart_added_at ON cart(added_at DESC)",
            
            # Discount indexes
            "CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code)",
            "CREATE INDEX IF NOT EXISTS idx_discount_active ON discount_codes(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_discount_usage_user ON discount_usage(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_discount_usage_order ON discount_usage(order_id)",
            
            # Pack indexes
            "CREATE INDEX IF NOT EXISTS idx_packs_product_id ON packs(product_id)",
            
            # Product indexes
            "CREATE INDEX IF NOT EXISTS idx_products_created ON products(created_at DESC)",
            
            # User indexes
            "CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at DESC)",
        ]
        
        for index_sql in indexes:
            try:
                self.cursor.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"⚠️ Failed to create index: {e}")
        
        self.conn.commit()
        logger.info("✅ Advanced indexes created")
    
    def _analyze_database(self):
        """تحلیل دیتابیس برای بهینه‌سازی query planner"""
        try:
            self.cursor.execute("ANALYZE")
            self.conn.commit()
            logger.info("✅ Database analyzed")
        except Exception as e:
            logger.warning(f"⚠️ Failed to analyze database: {e}")
    
    # Batch Operations
    
    def batch_insert_packs(self, product_id: int, packs: List[Tuple[str, int, float]]) -> List[int]:
        """Batch insert برای پک‌ها"""
        pack_ids = []
        
        try:
            with self.transaction(immediate=True) as cursor:
                for name, quantity, price in packs:
                    cursor.execute(
                        "INSERT INTO packs (product_id, name, quantity, price) VALUES (?, ?, ?, ?)",
                        (product_id, name, quantity, price)
                    )
                    pack_ids.append(cursor.lastrowid)
            
            self._invalidate_cache(f"packs:{product_id}")
            logger.info(f"✅ Batch inserted {len(packs)} packs for product {product_id}")
            
            return pack_ids
        
        except Exception as e:
            logger.error(f"❌ Batch insert failed: {e}")
            raise
    
    def batch_update_order_status(self, order_ids: List[int], status: str):
        """Batch update برای وضعیت سفارشات"""
        try:
            with self.transaction(immediate=True) as cursor:
                placeholders = ','.join('?' * len(order_ids))
                cursor.execute(
                    f"UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                    [status] + order_ids
                )
            
            self._invalidate_cache("stats:")
            logger.info(f"✅ Batch updated {len(order_ids)} orders to status: {status}")
        
        except Exception as e:
            logger.error(f"❌ Batch update failed: {e}")
            raise
    
    # محصولات
    
    def add_product(self, name: str, description: str, photo_id: str) -> int:
        try:
            with self.transaction(immediate=True) as cursor:
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
    
    @lru_cache(maxsize=128)
    def get_product(self, product_id: int):
        """با LRU cache"""
        self.cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return self.cursor.fetchone()
    
    def get_all_products(self) -> List:
        """با query caching"""
        cache_key = "all_products"
        return self._get_cached_query(
            cache_key,
            "SELECT * FROM products ORDER BY created_at DESC"
        )
    
    def update_product_name(self, product_id: int, name: str):
        with self.transaction(immediate=True) as cursor:
            cursor.execute("UPDATE products SET name = ? WHERE id = ?", (name, product_id))
        
        self._invalidate_cache(f"product:{product_id}")
        self._invalidate_cache("products:")
        self.get_product.cache_clear()
    
    def update_product_description(self, product_id: int, description: str):
        with self.transaction(immediate=True) as cursor:
            cursor.execute("UPDATE products SET description = ? WHERE id = ?", (description, product_id))
        
        self._invalidate_cache(f"product:{product_id}")
        self.get_product.cache_clear()
    
    def update_product_photo(self, product_id: int, photo_id: str):
        with self.transaction(immediate=True) as cursor:
            cursor.execute("UPDATE products SET photo_id = ? WHERE id = ?", (photo_id, product_id))
        
        self._invalidate_cache(f"product:{product_id}")
        self.get_product.cache_clear()
    
    def save_channel_message_id(self, product_id: int, message_id: int) -> bool:
        try:
            with self.transaction(immediate=True) as cursor:
                cursor.execute(
                    "UPDATE products SET channel_message_id = ? WHERE id = ?",
                    (message_id, product_id)
                )
            
            # تایید ذخیره
            self.cursor.execute("SELECT channel_message_id FROM products WHERE id = ?", (product_id,))
            saved_id = self.cursor.fetchone()
            
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
        with self.transaction(immediate=True) as cursor:
            cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
            cursor.execute("DELETE FROM packs WHERE product_id = ?", (product_id,))
        
        self._invalidate_cache(f"product:{product_id}")
        self._invalidate_cache(f"packs:{product_id}")
        self._invalidate_cache("products:")
        self.get_product.cache_clear()
    
    # پک‌ها
    
    def add_pack(self, product_id: int, name: str, quantity: int, price: float) -> int:
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                "INSERT INTO packs (product_id, name, quantity, price) VALUES (?, ?, ?, ?)",
                (product_id, name, quantity, price)
            )
            pack_id = cursor.lastrowid
        
        self._invalidate_cache(f"packs:{product_id}")
        return pack_id
    
    def get_packs(self, product_id: int) -> List:
        """با query caching"""
        cache_key = f"packs:{product_id}"
        return self._get_cached_query(
            cache_key,
            "SELECT * FROM packs WHERE product_id = ? ORDER BY created_at",
            (product_id,)
        )
    
    def get_pack(self, pack_id: int):
        self.cursor.execute("SELECT * FROM packs WHERE id = ?", (pack_id,))
        return self.cursor.fetchone()
    
    def update_pack(self, pack_id: int, name: str, quantity: int, price: float):
        pack = self.get_pack(pack_id)
        if pack:
            product_id = pack[1]
            with self.transaction(immediate=True) as cursor:
                cursor.execute(
                    "UPDATE packs SET name = ?, quantity = ?, price = ? WHERE id = ?",
                    (name, quantity, price, pack_id)
                )
            self._invalidate_cache(f"packs:{product_id}")
    
    def delete_pack(self, pack_id: int):
        pack = self.get_pack(pack_id)
        if pack:
            product_id = pack[1]
            with self.transaction(immediate=True) as cursor:
                cursor.execute("DELETE FROM packs WHERE id = ?", (pack_id,))
            self._invalidate_cache(f"packs:{product_id}")
    
    # کاربران
    
    def add_user(self, user_id: int, username: Optional[str], first_name: str):
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
    
    def update_user_info(self, user_id: int, phone=None, landline_phone=None, address=None, full_name=None, shop_name=None):
        updates = []
        params = []
        
        if phone:
            updates.append("phone = ?")
            params.append(phone)
        if landline_phone:
            updates.append("landline_phone = ?")
            params.append(landline_phone)
        if address:
            updates.append("address = ?")
            params.append(address)
        if full_name:
            updates.append("full_name = ?")
            params.append(full_name)
        if shop_name:
            updates.append("shop_name = ?")
            params.append(shop_name)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            
            with self.transaction(immediate=True) as cursor:
                cursor.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?",
                    params
                )
            
            self._invalidate_cache(f"user:{user_id}")
    
    def get_user(self, user_id: int):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def get_all_users(self) -> List:
        """با query caching"""
        cache_key = "all_users"
        return self._get_cached_query(cache_key, "SELECT * FROM users ORDER BY created_at DESC")
    
    # سبد خرید
    
    def add_to_cart(self, user_id: int, product_id: int, pack_id: int, quantity: int = 1):
    """✅ FIX: بدون استفاده از added_at در UPDATE"""
    pack = self.get_pack(pack_id)
    if not pack:
        return
    
    pack_quantity = pack[3]
    actual_quantity = quantity * pack_quantity
    
    with self.transaction(immediate=True) as cursor:
        # بررسی وجود
        cursor.execute(
            "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ? AND pack_id = ?",
            (user_id, product_id, pack_id)
        )
        existing = cursor.fetchone()
        
        if existing:
            new_quantity = existing[1] + actual_quantity
            # ✅ FIX: بدون added_at
            cursor.execute(
                "UPDATE cart SET quantity = ? WHERE id = ?",
                (new_quantity, existing[0])
            )
        else:
            cursor.execute(
                "INSERT INTO cart (user_id, product_id, pack_id, quantity) VALUES (?, ?, ?, ?)",
                (user_id, product_id, pack_id, actual_quantity)
            )
    
    def get_cart(self, user_id: int) -> List:
    """✅ FIX: بدون ORDER BY added_at"""
    self.clean_invalid_cart_items(user_id)
    
    cache_key = f"cart_items:{user_id}"
    return self._get_cached_query(
        cache_key,
        """
        SELECT c.id, p.name, pk.name, pk.quantity, pk.price, c.quantity
        FROM cart c
        JOIN products p ON c.product_id = p.id
        JOIN packs pk ON c.pack_id = pk.id
        WHERE c.user_id = ?
        ORDER BY c.id DESC
        """,
        (user_id,)
    )
    
    def clear_cart(self, user_id: int):
        with self.transaction(immediate=True) as cursor:
            cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        self._invalidate_cache(f"cart:{user_id}")
    
    def remove_from_cart(self, cart_id: int):
        with self.transaction(immediate=True) as cursor:
            cursor.execute("SELECT user_id FROM cart WHERE id = ?", (cart_id,))
            result = cursor.fetchone()
            
            cursor.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        
        if result:
            self._invalidate_cache(f"cart:{result[0]}")
    
    # سفارشات
    
    def create_order(self, user_id: int, items: List[dict], total_price: float, 
                    discount_amount: float = 0, final_price: Optional[float] = None, 
                    discount_code: Optional[str] = None) -> int:
        """با transaction optimization"""
        items_json = json.dumps(items, ensure_ascii=False)
        if final_price is None:
            final_price = total_price - discount_amount
        
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                """INSERT INTO orders 
                (user_id, items, total_price, discount_amount, final_price, discount_code) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, items_json, total_price, discount_amount, final_price, discount_code)
            )
            order_id = cursor.lastrowid
        
        self._invalidate_cache("stats:")
        return order_id
    
    def get_order(self, order_id: int):
        self.cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return self.cursor.fetchone()
    
    def update_order_status(self, order_id: int, status: str):
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, order_id)
            )
        self._invalidate_cache("stats:")
    
    def add_receipt(self, order_id: int, photo_id: str):
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                "UPDATE orders SET receipt_photo = ?, status = 'receipt_sent', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (photo_id, order_id)
            )
    
    def update_shipping_method(self, order_id: int, method: str):
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                "UPDATE orders SET shipping_method = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (method, order_id)
            )
    
    def get_pending_orders(self) -> List:
        """با index optimization"""
        return self._get_cached_query(
            "pending_orders",
            "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC"
        )
    
    def get_waiting_payment_orders(self) -> List:
        return self._get_cached_query(
            "waiting_payment_orders",
            "SELECT * FROM orders WHERE status = 'waiting_payment' ORDER BY created_at DESC"
        )
    
    def get_user_orders(self, user_id: int) -> List:
        """با composite index"""
        cache_key = f"user_orders:{user_id}"
        return self._get_cached_query(
            cache_key,
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
    
    # تخفیف
    
    def create_discount(self, code: str, type: str, value: float, min_purchase: float = 0, 
                       max_discount: Optional[float] = None, usage_limit: Optional[int] = None, 
                       start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                """INSERT INTO discount_codes 
                (code, type, value, min_purchase, max_discount, usage_limit, start_date, end_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, type, value, min_purchase, max_discount, usage_limit, start_date, end_date)
            )
            discount_id = cursor.lastrowid
        return discount_id
    
    def get_discount(self, code: str):
        self.cursor.execute(
            "SELECT * FROM discount_codes WHERE code = ? AND is_active = 1",
            (code,)
        )
        return self.cursor.fetchone()
    
    def get_all_discounts(self) -> List:
        return self._get_cached_query(
            "all_discounts",
            "SELECT * FROM discount_codes ORDER BY created_at DESC"
        )
    
    def use_discount(self, user_id: int, discount_code: str, order_id: int):
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                "INSERT INTO discount_usage (user_id, discount_code, order_id) VALUES (?, ?, ?)",
                (user_id, discount_code, order_id)
            )
            cursor.execute(
                "UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?",
                (discount_code,)
            )
    
    def toggle_discount(self, discount_id: int):
        with self.transaction(immediate=True) as cursor:
            cursor.execute(
                "UPDATE discount_codes SET is_active = 1 - is_active WHERE id = ?",
                (discount_id,)
            )
    
    def delete_discount(self, discount_id: int):
        with self.transaction(immediate=True) as cursor:
            cursor.execute("DELETE FROM discount_codes WHERE id = ?", (discount_id,))
    
    # آمار
    
    def get_statistics(self) -> Dict:
        """بهینه شده با single query برای multiple stats"""
        stats = {}
        
        # استفاده از CTE برای بهینه‌سازی
        query = """
        WITH order_stats AS (
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN DATE(created_at) = DATE('now') THEN 1 END) as today,
                COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-7 days') THEN 1 END) as week,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                SUM(CASE WHEN status IN ('confirmed', 'payment_confirmed') THEN final_price ELSE 0 END) as total_income,
                SUM(CASE WHEN status IN ('confirmed', 'payment_confirmed') AND DATE(created_at) = DATE('now') THEN final_price ELSE 0 END) as today_income,
                SUM(CASE WHEN status IN ('confirmed', 'payment_confirmed') AND DATE(created_at) >= DATE('now', '-7 days') THEN final_price ELSE 0 END) as week_income
            FROM orders
        ),
        user_stats AS (
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN DATE(created_at) >= DATE('now', '-7 days') THEN 1 END) as week_new
            FROM users
        ),
        product_stats AS (
            SELECT COUNT(*) as total FROM products
        )
        SELECT * FROM order_stats, user_stats, product_stats
        """
        
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        
        if row:
            stats['total_orders'] = row[0]
            stats['today_orders'] = row[1]
            stats['week_orders'] = row[2]
            stats['pending_orders'] = row[3]
            stats['total_income'] = row[4] or 0
            stats['today_income'] = row[5] or 0
            stats['week_income'] = row[6] or 0
            stats['total_users'] = row[7]
            stats['week_new_users'] = row[8]
            stats['total_products'] = row[9]
        
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
    
    def get_cache_stats(self) -> Dict:
        """آمار کش query"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'total_requests': total,
            'hit_rate': round(hit_rate, 2),
            'cached_queries': len(self._query_cache)
        }
    
    def close(self):
        """بستن connection با cleanup کامل"""
        try:
            # پاک کردن cache
            self._query_cache.clear()
            self.get_product.cache_clear()
            
            # نمایش آمار
            cache_stats = self.get_cache_stats()
            pool_stats = self.pool.get_stats()
            
            logger.info(f"📊 Query Cache Stats: {cache_stats}")
            logger.info(f"📊 Connection Pool Stats: {pool_stats}")
            
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
            if hasattr(self, 'pool') and self.pool:
                self.pool.cleanup_all()
            
            logger.info("✅ Database connections closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing database: {e}")
