"""
سیستم Rate Limiting برای جلوگیری از spam و حملات DoS
✅ FIX: Smart Alert - فقط یه بار alert میده، بعد silent
✅ FIX: Admin Bypass خودکار
✅ FIX: حذف bypass_rate_limit_for_admin (deprecated)
🛡️ محدودیت‌ها:
- 20 پیام در دقیقه (سراسری)
- 3 سفارش در ساعت
- 5 امتحان کد تخفیف در دقیقه
"""
import time
import logging
from functools import wraps
from logger import log_rate_limit
from collections import defaultdict, deque
from typing import Callable, Dict, Tuple
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID

logger = logging.getLogger(__name__)


class RateLimiter:
    """کلاس مدیریت Rate Limiting با Smart Alert"""
    
    def __init__(self):
        # ذخیره زمان‌های درخواست هر کاربر
        self._user_requests: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # شمارنده برای عملیات خاص
        self._action_requests: Dict[Tuple[int, str], deque] = defaultdict(lambda: deque(maxlen=50))
        
        # ✅ FIX: ذخیره آخرین باری که alert داده شده
        # {user_id: last_alert_time}
        self._last_alert: Dict[int, float] = {}
        
        # ✅ FIX: حداقل فاصله بین alertها (ثانیه)
        self.ALERT_COOLDOWN = 10
    
    def _cleanup_old_requests(self, user_id: int, window_seconds: int):
        """حذف درخواست‌های قدیمی خارج از بازه زمانی"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        while self._user_requests[user_id] and self._user_requests[user_id][0] < cutoff_time:
            self._user_requests[user_id].popleft()
    
    def _cleanup_action_requests(self, user_id: int, action: str, window_seconds: int):
        """حذف درخواست‌های قدیمی برای یک عملیات خاص"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        key = (user_id, action)
        
        while self._action_requests[key] and self._action_requests[key][0] < cutoff_time:
            self._action_requests[key].popleft()
    
    def _should_show_alert(self, user_id: int) -> bool:
        """
        ✅ FIX: بررسی اینکه باید alert نشون بده یا نه
        
        Returns:
            True: نشون بده (اولین بار یا بعد از cooldown)
            False: نشون نده (silent)
        """
        current_time = time.time()
        last_alert = self._last_alert.get(user_id, 0)
        
        # اگه cooldown گذشته یا اولین باره
        if current_time - last_alert >= self.ALERT_COOLDOWN:
            self._last_alert[user_id] = current_time
            return True
        
        return False
    
    def check_rate_limit(self, user_id: int, max_requests: int = 10, 
                        window_seconds: int = 10) -> Tuple[bool, int, bool]:
        """
        بررسی محدودیت کلی
        ✅ FIX: برمیگردونه (allowed, remaining_time, show_alert)
        
        Args:
            user_id: شناسه کاربر
            max_requests: حداکثر تعداد درخواست
            window_seconds: بازه زمانی (ثانیه)
            
        Returns:
            (allowed, remaining_time, show_alert)
        """
        self._cleanup_old_requests(user_id, window_seconds)
        
        request_count = len(self._user_requests[user_id])
        
        if request_count >= max_requests:
            oldest_request = self._user_requests[user_id][0]
            remaining_time = int(window_seconds - (time.time() - oldest_request)) + 1
            
            # لاگ محدودیت
            log_rate_limit(user_id, "general", remaining_time)
            
            # ✅ FIX: چک کن باید alert بده یا نه
            show_alert = self._should_show_alert(user_id)
            
            return False, remaining_time, show_alert
        
        # ثبت درخواست جدید
        self._user_requests[user_id].append(time.time())
        return True, 0, False
    
    def check_action_limit(self, user_id: int, action: str, 
                          max_requests: int, window_seconds: int) -> Tuple[bool, int, bool]:
        """
        بررسی محدودیت برای یک عملیات خاص
        ✅ FIX: برمیگردونه (allowed, remaining_time, show_alert)
        
        Args:
            user_id: شناسه کاربر
            action: نام عملیات (مثل 'order', 'discount')
            max_requests: حداکثر تعداد
            window_seconds: بازه زمانی (ثانیه)
            
        Returns:
            (allowed, remaining_time, show_alert)
        """
        self._cleanup_action_requests(user_id, action, window_seconds)
        key = (user_id, action)
        
        request_count = len(self._action_requests[key])
        
        if request_count >= max_requests:
            oldest_request = self._action_requests[key][0]
            remaining_time = int(window_seconds - (time.time() - oldest_request)) + 1
            
            log_rate_limit(user_id, action, remaining_time)
            logger.warning(f"⚠️ Action limit exceeded for user {user_id}, action '{action}': {request_count}/{max_requests}")
            
            # ✅ FIX: چک کن باید alert بده یا نه
            show_alert = self._should_show_alert(user_id)
            
            return False, remaining_time, show_alert
        
        # ثبت درخواست جدید
        self._action_requests[key].append(time.time())
        return True, 0, False
    
    def reset_user(self, user_id: int):
        """ریست کردن محدودیت‌های یک کاربر (برای ادمین)"""
        if user_id in self._user_requests:
            del self._user_requests[user_id]
        
        keys_to_delete = [key for key in self._action_requests if key[0] == user_id]
        for key in keys_to_delete:
            del self._action_requests[key]
        
        if user_id in self._last_alert:
            del self._last_alert[user_id]
        
        logger.info(f"✅ Rate limits reset for user {user_id}")
    
    def cleanup_stale_users(self, max_idle_seconds: int = 3600):
        """
        ✅ FIX #5: حذف کاربرانی که مدت‌هاست فعال نیستن (جلوگیری از Memory Leak)
        
        این تابع باید هر ساعت یکبار از طریق JobQueue اجرا بشه:
            application.job_queue.run_repeating(
                lambda ctx: rate_limiter.cleanup_stale_users(),
                interval=3600
            )
        """
        now = time.time()
        
        stale_users = [
            uid for uid, reqs in self._user_requests.items()
            if not reqs or (now - max(reqs)) > max_idle_seconds
        ]
        
        for uid in stale_users:
            del self._user_requests[uid]
            if uid in self._last_alert:
                del self._last_alert[uid]
        
        stale_action_keys = [
            key for key, reqs in self._action_requests.items()
            if not reqs or (now - max(reqs)) > max_idle_seconds
        ]
        
        for key in stale_action_keys:
            del self._action_requests[key]
        
        if stale_users or stale_action_keys:
            logger.info(f"🧹 RateLimiter cleanup: {len(stale_users)} users, {len(stale_action_keys)} actions removed")
    
    def get_stats(self, user_id: int) -> dict:
        """دریافت آمار محدودیت‌های یک کاربر"""
        stats = {
            'user_id': user_id,
            'general_requests': len(self._user_requests.get(user_id, [])),
            'actions': {},
            'last_alert': self._last_alert.get(user_id, 0)
        }
        
        for (uid, action), requests in self._action_requests.items():
            if uid == user_id:
                stats['actions'][action] = len(requests)
        
        return stats


# نمونه سراسری
rate_limiter = RateLimiter()


# ==================== Helper Functions ====================

def is_admin(user_id: int) -> bool:
    """بررسی ادمین بودن کاربر"""
    return user_id == ADMIN_ID


# ==================== Decorators ====================

def rate_limit(max_requests: int = 10, window_seconds: int = 10):
    """
    دکوریتور محدودسازی کلی
    ✅ FIX: Smart Alert - فقط یه بار alert، بعد silent
    ✅ FIX: Admin Bypass خودکار
    
    مثال:
        @rate_limit(max_requests=5, window_seconds=60)
        async def my_handler(update, context):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user:
                return await func(update, context, *args, **kwargs)
            
            user_id = update.effective_user.id
            
            # ✅ Admin Bypass
            if is_admin(user_id):
                logger.debug(f"✅ Admin {user_id} bypassed rate limit")
                return await func(update, context, *args, **kwargs)
            
            # ✅ FIX: دریافت show_alert
            allowed, remaining_time, show_alert = rate_limiter.check_rate_limit(
                user_id, max_requests, window_seconds
            )
            
            if not allowed:
                # ✅ FIX: فقط اگه show_alert=True باشه، پیام بده
                if show_alert:
                    warning_msg = (
                        f"⚠️ **شما خیلی سریع درخواست می‌فرستید!**\n\n"
                        f"لطفاً {remaining_time} ثانیه صبر کنید.\n\n"
                        f"📌 محدودیت: {max_requests} درخواست در {window_seconds} ثانیه"
                    )
                    
                    try:
                        if update.message:
                            await update.message.reply_text(warning_msg, parse_mode='Markdown')
                        elif update.callback_query:
                            await update.callback_query.answer(
                                f"⚠️ لطفاً {remaining_time} ثانیه صبر کنید",
                                show_alert=True
                            )
                    except Exception as e:
                        logger.error(f"❌ Error sending rate limit message: {e}")
                else:
                    # ✅ Silent mode - هیچ کاری نکن
                    logger.debug(f"🔇 Silent rate limit for user {user_id}")
                
                return None
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def action_limit(action: str, max_requests: int, window_seconds: int):
    """
    دکوریتور محدودسازی برای عملیات خاص
    ✅ FIX: Smart Alert - فقط یه بار alert، بعد silent
    ✅ FIX: Admin Bypass خودکار
    
    مثال:
        @action_limit('order', max_requests=3, window_seconds=3600)
        async def create_order(update, context):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user:
                return await func(update, context, *args, **kwargs)
            
            user_id = update.effective_user.id
            
            # ✅ Admin Bypass
            if is_admin(user_id):
                logger.debug(f"✅ Admin {user_id} bypassed action limit for '{action}'")
                return await func(update, context, *args, **kwargs)
            
            # ✅ FIX: دریافت show_alert
            allowed, remaining_time, show_alert = rate_limiter.check_action_limit(
                user_id, action, max_requests, window_seconds
            )
            
            if not allowed:
                # ✅ FIX: فقط اگه show_alert=True باشه، پیام بده
                if show_alert:
                    minutes = remaining_time // 60
                    seconds = remaining_time % 60
                    
                    time_str = ""
                    if minutes > 0:
                        time_str += f"{minutes} دقیقه"
                        if seconds > 0:
                            time_str += f" و {seconds} ثانیه"
                    else:
                        time_str = f"{seconds} ثانیه"
                    
                    action_names = {
                        'order': 'ثبت سفارش',
                        'discount': 'امتحان کد تخفیف',
                        'cart': 'افزودن به سبد'
                    }
                    
                    action_display = action_names.get(action, action)
                    
                    warning_msg = (
                        f"⚠️ **محدودیت {action_display}**\n\n"
                        f"شما به حداکثر تعداد مجاز رسیده‌اید.\n\n"
                        f"⏰ لطفاً {time_str} صبر کنید.\n\n"
                        f"📌 محدودیت: {max_requests} بار در هر "
                    )
                    
                    if window_seconds >= 3600:
                        warning_msg += f"{window_seconds // 3600} ساعت"
                    elif window_seconds >= 60:
                        warning_msg += f"{window_seconds // 60} دقیقه"
                    else:
                        warning_msg += f"{window_seconds} ثانیه"
                    
                    try:
                        if update.message:
                            await update.message.reply_text(warning_msg, parse_mode='Markdown')
                        elif update.callback_query:
                            await update.callback_query.answer(
                                f"⚠️ لطفاً {time_str} صبر کنید",
                                show_alert=True
                            )
                    except Exception as e:
                        logger.error(f"❌ Error sending action limit message: {e}")
                else:
                    # ✅ Silent mode
                    logger.debug(f"🔇 Silent action limit for user {user_id}, action '{action}'")
                
                logger.warning(f"⚠️ User {user_id} hit action limit for '{action}'")
                return None
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# ✅ FIX: حذف کامل bypass_rate_limit_for_admin
# دیگه لازم نیست چون Admin Bypass خودکاره!
