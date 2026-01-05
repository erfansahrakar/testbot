"""
🚀 سیستم کش پیشرفته با LRU و TTL
✅ LRU Cache با eviction policy
✅ TTL (Time To Live) پیشرفته
✅ Automatic cleanup
✅ Cache statistics
✅ Memory-efficient
"""
import time
import logging
from typing import Any, Optional, Dict, Callable, List, Tuple
from functools import wraps
from datetime import datetime
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


class CacheEntry:
    """یک رکورد کش با metadata کامل"""
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.ttl = ttl
        self.hits = 0
        self.size = self._estimate_size(value)
    
    def _estimate_size(self, value: Any) -> int:
        """تخمین حجم value"""
        try:
            import sys
            return sys.getsizeof(value)
        except:
            return 0
    
    def is_expired(self) -> bool:
        """بررسی انقضای کش"""
        if self.ttl == 0:  # بی‌نهایت
            return False
        return (time.time() - self.created_at) > self.ttl
    
    def get_age(self) -> float:
        """سن کش به ثانیه"""
        return time.time() - self.created_at
    
    def access(self):
        """ثبت دسترسی به cache"""
        self.last_accessed = time.time()
        self.hits += 1


class LRUCache:
    """🆕 LRU Cache با محدودیت حافظه"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self._cache = OrderedDict()
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._lock = threading.Lock()
        self._total_memory = 0
        
        # آمار
        self._evictions = 0
        self._memory_evictions = 0
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """دریافت از cache با LRU update"""
        with self._lock:
            if key not in self._cache:
                return None
            
            # Move to end (most recently used)
            entry = self._cache.pop(key)
            self._cache[key] = entry
            entry.access()
            
            return entry
    
    def set(self, key: str, entry: CacheEntry):
        """ذخیره در cache با LRU eviction"""
        with self._lock:
            # اگر قبلاً وجود داشت، حذف کن
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._total_memory -= old_entry.size
            
            # بررسی محدودیت تعداد
            while len(self._cache) >= self.max_size:
                self._evict_lru()
            
            # بررسی محدودیت حافظه
            while self._total_memory + entry.size > self.max_memory_bytes and self._cache:
                self._evict_lru(memory=True)
            
            # اضافه کردن entry جدید
            self._cache[key] = entry
            self._total_memory += entry.size
    
    def _evict_lru(self, memory: bool = False):
        """حذف قدیمی‌ترین item"""
        if not self._cache:
            return
        
        # حذف اولین item (قدیمی‌ترین)
        key, entry = self._cache.popitem(last=False)
        self._total_memory -= entry.size
        self._evictions += 1
        
        if memory:
            self._memory_evictions += 1
        
        logger.debug(f"🗑 LRU evicted: {key} (reason: {'memory' if memory else 'size'})")
    
    def delete(self, key: str) -> bool:
        """حذف از cache"""
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._total_memory -= entry.size
                return True
            return False
    
    def clear(self):
        """پاک کردن کل cache"""
        with self._lock:
            self._cache.clear()
            self._total_memory = 0
    
    def get_stats(self) -> Dict:
        """آمار LRU cache"""
        with self._lock:
            return {
                'size': len(self._cache),
                'memory_mb': round(self._total_memory / (1024 * 1024), 2),
                'evictions': self._evictions,
                'memory_evictions': self._memory_evictions
            }
    
    def items(self):
        """دریافت تمام items"""
        with self._lock:
            return list(self._cache.items())


class CacheManager:
    """🚀 مدیریت کش پیشرفته با LRU"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self._lru = LRUCache(max_size, max_memory_mb)
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0,
            'expirations': 0
        }
        self._lock = threading.Lock()
        
        logger.info(f"✅ CacheManager initialized (max_size={max_size}, max_memory={max_memory_mb}MB)")
    
    def get(self, key: str) -> Optional[Any]:
        """دریافت از کش با expiration check"""
        entry = self._lru.get(key)
        
        if entry is None:
            with self._lock:
                self._stats['misses'] += 1
            return None
        
        # بررسی انقضا
        if entry.is_expired():
            with self._lock:
                self._stats['expirations'] += 1
            self._lru.delete(key)
            return None
        
        # Cache hit
        with self._lock:
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
        entry = CacheEntry(value, ttl)
        self._lru.set(key, entry)
        
        with self._lock:
            self._stats['sets'] += 1
        
        logger.debug(f"💾 Cache SET: {key} (ttl: {ttl}s, size: {entry.size} bytes)")
    
    def invalidate(self, key: str):
        """حذف از کش"""
        if self._lru.delete(key):
            with self._lock:
                self._stats['invalidations'] += 1
            logger.debug(f"🗑 Cache INVALIDATE: {key}")
    
    def invalidate_pattern(self, pattern: str):
        """حذف تمام کش‌های با الگوی مشخص"""
        keys_to_delete = []
        
        for key, entry in self._lru.items():
            if pattern in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            self.invalidate(key)
        
        logger.debug(f"🗑 Cache INVALIDATE PATTERN: {pattern} ({len(keys_to_delete)} items)")
    
    def clear(self):
        """پاک کردن تمام کش"""
        lru_stats = self._lru.get_stats()
        self._lru.clear()
        logger.info(f"🗑 Cache CLEARED: {lru_stats['size']} items removed ({lru_stats['memory_mb']}MB freed)")
    
    def cleanup(self):
        """🆕 حذف کش‌های منقضی شده با progress"""
        expired_keys = []
        
        for key, entry in self._lru.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            self._lru.delete(key)
            with self._lock:
                self._stats['expirations'] += 1
        
        if expired_keys:
            logger.info(f"🧹 Cache CLEANUP: {len(expired_keys)} expired items removed")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """آمار کش با جزئیات بیشتر"""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            lru_stats = self._lru.get_stats()
            
            return {
                **self._stats,
                'total_requests': total_requests,
                'hit_rate': round(hit_rate, 2),
                'cache_size': lru_stats['size'],
                'memory_mb': lru_stats['memory_mb'],
                'evictions': lru_stats['evictions'],
                'memory_evictions': lru_stats['memory_evictions']
            }
    
    def get_info(self, key: str) -> Optional[Dict]:
        """اطلاعات یک کش"""
        entry = self._lru.get(key)
        
        if entry is None:
            return None
        
        return {
            'age_seconds': entry.get_age(),
            'ttl': entry.ttl,
            'hits': entry.hits,
            'size_bytes': entry.size,
            'last_accessed': datetime.fromtimestamp(entry.last_accessed).isoformat(),
            'expired': entry.is_expired()
        }
    
    def get_top_keys(self, limit: int = 10) -> List[Tuple[str, int]]:
        """🆕 دریافت پرکاربردترین کلیدها"""
        items_with_hits = []
        
        for key, entry in self._lru.items():
            items_with_hits.append((key, entry.hits))
        
        # مرتب‌سازی بر اساس hits
        items_with_hits.sort(key=lambda x: x[1], reverse=True)
        
        return items_with_hits[:limit]


# ==================== Cache Manager سراسری ====================

cache_manager = CacheManager(max_size=1000, max_memory_mb=100)


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
    """کش اختصاصی برای عملیات دیتابیس با بهینه‌سازی"""
    
    def __init__(self, db, cache_manager: CacheManager):
        self.db = db
        self.cache = cache_manager
    
    # محصولات
    
    @cached(ttl=600, key_prefix="product")
    def get_product(self, product_id: int):
        """دریافت محصول با کش خودکار"""
        return self.db.get_product(product_id)
    
    @cached(ttl=300, key_prefix="products")
    def get_all_products(self):
        """دریافت تمام محصولات با کش"""
        return self.db.get_all_products()
    
    def invalidate_product(self, product_id: int):
        """حذف کش محصول"""
        self.cache.invalidate(f"product:get_product:{product_id}")
        self.cache.invalidate_pattern("products:")
    
    # پک‌ها
    
    @cached(ttl=600, key_prefix="packs")
    def get_packs(self, product_id: int):
        """دریافت پک‌های محصول با کش"""
        return self.db.get_packs(product_id)
    
    def invalidate_packs(self, product_id: int):
        """حذف کش پک‌ها"""
        self.cache.invalidate(f"packs:get_packs:{product_id}")
    
    # آمار
    
    @cached(ttl=60, key_prefix="stats")
    def get_statistics(self):
        """دریافت آمار با کش کوتاه‌مدت"""
        return self.db.get_statistics()
    
    def invalidate_statistics(self):
        """حذف کش آمار"""
        self.cache.invalidate_pattern("stats:")
    
    # کاربران
    
    @cached(ttl=1800, key_prefix="user")
    def get_user(self, user_id: int):
        """دریافت کاربر با کش"""
        return self.db.get_user(user_id)
    
    def invalidate_user(self, user_id: int):
        """حذف کش کاربر"""
        self.cache.invalidate(f"user:get_user:{user_id}")
    
    # سبد خرید
    
    @cached(ttl=120, key_prefix="cart")
    def get_cart(self, user_id: int):
        """دریافت سبد خرید با کش"""
        return self.db.get_cart(user_id)
    
    def invalidate_cart(self, user_id: int):
        """حذف کش سبد خرید"""
        self.cache.invalidate(f"cart:get_cart:{user_id}")


# ==================== Auto Cleanup ====================

class CacheCleanupThread(threading.Thread):
    """🆕 Thread بهینه شده برای پاکسازی خودکار کش"""
    
    def __init__(self, cache_manager: CacheManager, interval: int = 300):
        super().__init__(daemon=True)
        self.cache_manager = cache_manager
        self.interval = interval
        self.running = True
        self.cleanup_count = 0
    
    def run(self):
        """اجرای پاکسازی دوره‌ای با آمار"""
        logger.info("✅ Cache cleanup thread started")
        
        while self.running:
            time.sleep(self.interval)
            try:
                removed = self.cache_manager.cleanup()
                self.cleanup_count += 1
                
                if removed > 0:
                    logger.info(f"🧹 Cleanup #{self.cleanup_count}: {removed} items removed")
                
                # نمایش آمار هر 10 cleanup
                if self.cleanup_count % 10 == 0:
                    stats = self.cache_manager.get_stats()
                    logger.info(f"📊 Cache Stats: {stats}")
                    
            except Exception as e:
                logger.error(f"❌ Error in cache cleanup: {e}")
    
    def stop(self):
        """توقف thread"""
        self.running = False
        logger.info(f"🛑 Cache cleanup thread stopped (total cleanups: {self.cleanup_count})")


# شروع خودکار پاکسازی
cleanup_thread = CacheCleanupThread(cache_manager, interval=300)
cleanup_thread.start()

logger.info("✅ Cache system initialized with LRU and auto-cleanup")
