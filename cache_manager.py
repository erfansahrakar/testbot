"""
سیستم کش برای کاهش فشار به دیتابیس
✅ کش محصولات
✅ کش آمار
✅ TTL (Time To Live)
✅ Invalidation خودکار
"""
import time
import logging
from typing import Any, Optional, Dict, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheEntry:
    """یک رکورد کش"""
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0
    
    def is_expired(self) -> bool:
        """بررسی انقضای کش"""
        if self.ttl == 0:  # بی‌نهایت
            return False
        return (time.time() - self.created_at) > self.ttl
    
    def get_age(self) -> float:
        """سن کش به ثانیه"""
        return time.time() - self.created_at


class CacheManager:
    """مدیریت کش"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0,
            'expirations': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """دریافت از کش"""
        if key not in self._cache:
            self._stats['misses'] += 1
            return None
        
        entry = self._cache[key]
        
        # بررسی انقضا
        if entry.is_expired():
            self._stats['expirations'] += 1
            del self._cache[key]
            return None
        
        # Cache hit
        entry.hits += 1
        self._stats['hits'] += 1
        
        logger.debug(f"📦 Cache HIT: {key} (age: {entry.get_age():.1f}s, hits: {entry.hits})")
        return entry.value
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """ذخیره در کش
        
        Args:
            key: کلید
            value: مقدار
            ttl: مدت اعتبار به ثانیه (0 = بی‌نهایت)
        """
        self._cache[key] = CacheEntry(value, ttl)
        self._stats['sets'] += 1
        
        logger.debug(f"💾 Cache SET: {key} (ttl: {ttl}s)")
    
    def invalidate(self, key: str):
        """حذف از کش"""
        if key in self._cache:
            del self._cache[key]
            self._stats['invalidations'] += 1
            logger.debug(f"🗑 Cache INVALIDATE: {key}")
    
    def invalidate_pattern(self, pattern: str):
        """حذف تمام کش‌های با الگوی مشخص"""
        keys_to_delete = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_delete:
            self.invalidate(key)
        
        logger.debug(f"🗑 Cache INVALIDATE PATTERN: {pattern} ({len(keys_to_delete)} items)")
    
    def clear(self):
        """پاک کردن تمام کش"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"🗑 Cache CLEARED: {count} items removed")
    
    def cleanup(self):
        """حذف کش‌های منقضی شده"""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        
        for key in expired_keys:
            del self._cache[key]
            self._stats['expirations'] += 1
        
        if expired_keys:
            logger.info(f"🧹 Cache CLEANUP: {len(expired_keys)} expired items removed")
    
    def get_stats(self) -> Dict:
        """آمار کش"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2),
            'cache_size': len(self._cache),
            'memory_items': sum(1 for _ in self._cache.values())
        }
    
    def get_info(self, key: str) -> Optional[Dict]:
        """اطلاعات یک کش"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        return {
            'age_seconds': entry.get_age(),
            'ttl': entry.ttl,
            'hits': entry.hits,
            'expired': entry.is_expired()
        }


# ==================== Cache Manager سراسری ====================

cache_manager = CacheManager()


# ==================== Cache Decorators ====================

def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator برای کش کردن خروجی تابع
    
    مثال:
        @cached(ttl=600, key_prefix="product")
        def get_product(product_id):
            return db.get_product(product_id)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # ساخت کلید کش
            # فقط از args استفاده می‌کنیم (نه kwargs) برای سادگی
            args_str = "_".join(str(arg) for arg in args if not callable(arg))
            cache_key = f"{key_prefix}:{func.__name__}:{args_str}"
            
            # بررسی کش
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # اجرای تابع
            result = func(*args, **kwargs)
            
            # ذخیره در کش
            cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(key_pattern: str):
    """
    Decorator برای حذف کش پس از اجرای تابع
    
    مثال:
        @invalidate_cache("product:*")
        def update_product(product_id, data):
            db.update_product(product_id, data)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            cache_manager.invalidate_pattern(key_pattern)
            return result
        
        return wrapper
    return decorator


# ==================== Cache Helpers برای دیتابیس ====================

class DatabaseCache:
    """کش اختصاصی برای عملیات دیتابیس"""
    
    def __init__(self, db, cache_manager: CacheManager):
        self.db = db
        self.cache = cache_manager
    
    # محصولات
    
    def get_product(self, product_id: int):
        """دریافت محصول با کش"""
        cache_key = f"product:{product_id}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        product = self.db.get_product(product_id)
        if product:
            self.cache.set(cache_key, product, ttl=600)  # 10 دقیقه
        
        return product
    
    def get_all_products(self):
        """دریافت تمام محصولات با کش"""
        cache_key = "products:all"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        products = self.db.get_all_products()
        self.cache.set(cache_key, products, ttl=300)  # 5 دقیقه
        
        return products
    
    def invalidate_product(self, product_id: int):
        """حذف کش محصول"""
        self.cache.invalidate(f"product:{product_id}")
        self.cache.invalidate("products:all")
    
    # پک‌ها
    
    def get_packs(self, product_id: int):
        """دریافت پک‌های محصول با کش"""
        cache_key = f"packs:{product_id}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        packs = self.db.get_packs(product_id)
        self.cache.set(cache_key, packs, ttl=600)  # 10 دقیقه
        
        return packs
    
    def invalidate_packs(self, product_id: int):
        """حذف کش پک‌ها"""
        self.cache.invalidate(f"packs:{product_id}")
    
    # آمار
    
    def get_statistics(self):
        """دریافت آمار با کش"""
        cache_key = "stats:main"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        stats = self.db.get_statistics()
        self.cache.set(cache_key, stats, ttl=60)  # 1 دقیقه
        
        return stats
    
    def invalidate_statistics(self):
        """حذف کش آمار"""
        self.cache.invalidate("stats:main")
    
    # کاربران
    
    def get_user(self, user_id: int):
        """دریافت کاربر با کش"""
        cache_key = f"user:{user_id}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        user = self.db.get_user(user_id)
        if user:
            self.cache.set(cache_key, user, ttl=1800)  # 30 دقیقه
        
        return user
    
    def invalidate_user(self, user_id: int):
        """حذف کش کاربر"""
        self.cache.invalidate(f"user:{user_id}")
    
    # سبد خرید
    
    def get_cart(self, user_id: int):
        """دریافت سبد خرید با کش"""
        cache_key = f"cart:{user_id}"
        
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        cart = self.db.get_cart(user_id)
        self.cache.set(cache_key, cart, ttl=120)  # 2 دقیقه
        
        return cart
    
    def invalidate_cart(self, user_id: int):
        """حذف کش سبد خرید"""
        self.cache.invalidate(f"cart:{user_id}")


# ==================== Auto Cleanup ====================

import threading

class CacheCleanupThread(threading.Thread):
    """Thread برای پاکسازی خودکار کش"""
    
    def __init__(self, cache_manager: CacheManager, interval: int = 300):
        super().__init__(daemon=True)
        self.cache_manager = cache_manager
        self.interval = interval
        self.running = True
    
    def run(self):
        """اجرای پاکسازی دوره‌ای"""
        while self.running:
            time.sleep(self.interval)
            try:
                self.cache_manager.cleanup()
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    def stop(self):
        """توقف thread"""
        self.running = False


# شروع خودکار پاکسازی
cleanup_thread = CacheCleanupThread(cache_manager, interval=300)
cleanup_thread.start()

logger.info("✅ Cache cleanup thread started")
