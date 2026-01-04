"""
سیستم Rate Limiting برای جلوگیری از spam و حملات DoS
🛡️ محدودیت‌ها:
- 10 پیام در 10 ثانیه
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

logger = logging.getLogger(__name__)


class RateLimiter:
    """کلاس مدیریت Rate Limiting"""
    
    def __init__(self):
        # ذخیره زمان‌های درخواست هر کاربر
        # {user_id: deque([timestamp1, timestamp2, ...])}
        self._user_requests: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # شمارنده برای عملیات خاص
        # {(user_id, action): deque([timestamp1, timestamp2, ...])}
        self._action_requests: Dict[Tuple[int, str], deque] = defaultdict(lambda: deque(maxlen=50))
    
    def _cleanup_old_requests(self, user_id: int, window_seconds: int):
        """حذف درخواست‌های قدیمی خارج از بازه زمانی"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # پاکسازی درخواست‌های عمومی
        while self._user_requests[user_id] and self._user_requests[user_id][0] < cutoff_time:
            self._user_requests[user_id].popleft()
    
    def _cleanup_action_requests(self, user_id: int, action: str, window_seconds: int):
        """حذف درخواست‌های قدیمی برای یک عملیات خاص"""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        key = (user_id, action)
        
        while self._action_requests[key] and self._action_requests[key][0] < cutoff_time:
            self._action_requests[key].popleft()
    
    def check_rate_limit(self, user_id: int, max_requests: int = 10, 
                        window_seconds: int = 10) -> Tuple[bool, int]:
        """
        بررسی محدودیت کلی
        
        Args:
            user_id: شناسه کاربر
            max_requests: حداکثر تعداد درخواست
            window_seconds: بازه زمانی (ثانیه)
            
        Returns:
            (allowed, remaining_time)
        """
        self._cleanup_old_requests(user_id, window_seconds)
        
        request_count = len(self._user_requests[user_id])
        
        if request_count >= max_requests:
            oldest_request = self._user_requests[user_id][0]
            remaining_time = int(window_seconds - (time.time() - oldest_request)) + 1
    
            # 🆕 لاگ محدودیت
            log_rate_limit(user_id, "general", remaining_time)
    
            return False, remaining_time
        
        # ثبت درخواست جدید
        self._user_requests[user_id].append(time.time())
        return True, 0
    
    def check_action_limit(self, user_id: int, action: str, 
                          max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        بررسی محدودیت برای یک عملیات خاص
        
        Args:
            user_id: شناسه کاربر
            action: نام عملیات (مثل 'order', 'discount')
            max_requests: حداکثر تعداد
            window_seconds: بازه زمانی (ثانیه)
            
        Returns:
            (allowed, remaining_time)
        """
        self._cleanup_action_requests(user_id, action, window_seconds)
        key = (user_id, action)
        
        request_count = len(self._action_requests[key])
        
        if request_count >= max_requests:
            oldest_request = self._action_requests[key][0]
            remaining_time = int(window_seconds - (time.time() - oldest_request)) + 1
            logger.warning(f"Action limit exceeded for user {user_id}, action '{action}': {request_count}/{max_requests}")
            return False, remaining_time
        
        # ثبت درخواست جدید
        self._action_requests[key].append(time.time())
        return True, 0
    
    def reset_user(self, user_id: int):
        """ریست کردن محدودیت‌های یک کاربر (برای ادمین)"""
        if user_id in self._user_requests:
            del self._user_requests[user_id]
        
        # حذف تمام action های این کاربر
        keys_to_delete = [key for key in self._action_requests if key[0] == user_id]
        for key in keys_to_delete:
            del self._action_requests[key]
        
        logger.info(f"Rate limits reset for user {user_id}")


# نمونه سراسری
rate_limiter = RateLimiter()


# ==================== Decorators ====================

def rate_limit(max_requests: int = 10, window_seconds: int = 10):
    """
    دکوریتور محدودسازی کلی
    
    مثال:
        @rate_limit(max_requests=5, window_seconds=60)
        async def my_handler(update, context):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            allowed, remaining_time = rate_limiter.check_rate_limit(
                user_id, max_requests, window_seconds
            )
            
            if not allowed:
                warning_msg = (
                    f"⚠️ **شما خیلی سریع درخواست می‌فرستید!**\n\n"
                    f"لطفاً {remaining_time} ثانیه صبر کنید.\n\n"
                    f"📌 محدودیت: {max_requests} درخواست در {window_seconds} ثانیه"
                )
                
                if update.message:
                    await update.message.reply_text(warning_msg, parse_mode='Markdown')
                elif update.callback_query:
                    await update.callback_query.answer(
                        f"⚠️ لطفاً {remaining_time} ثانیه صبر کنید",
                        show_alert=True
                    )
                
                return None
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def action_limit(action: str, max_requests: int, window_seconds: int):
    """
    دکوریتور محدودسازی برای عملیات خاص
    
    مثال:
        @action_limit('order', max_requests=3, window_seconds=3600)
        async def create_order(update, context):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            allowed, remaining_time = rate_limiter.check_action_limit(
                user_id, action, max_requests, window_seconds
            )
            
            if not allowed:
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
                
                warning_msg = (
                    f"⚠️ **محدودیت {action_names.get(action, action)}**\n\n"
                    f"شما به حداکثر تعداد مجاز رسیده‌اید.\n\n"
                    f"⏰ لطفاً {time_str} صبر کنید.\n\n"
                    f"📌 محدودیت: {max_requests} بار در هر "
                    f"{window_seconds // 60} دقیقه" if window_seconds >= 60 
                    else f"{window_seconds} ثانیه"
                )
                
                if update.message:
                    await update.message.reply_text(warning_msg, parse_mode='Markdown')
                elif update.callback_query:
                    await update.callback_query.answer(
                        f"⚠️ لطفاً {time_str} صبر کنید",
                        show_alert=True
                    )
                
                logger.warning(f"User {user_id} hit action limit for '{action}'")
                return None
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# ==================== Helper Functions ====================

def is_admin(user_id: int, admin_id: int) -> bool:
    """بررسی ادمین بودن کاربر"""
    return user_id == admin_id


def bypass_rate_limit_for_admin(admin_id: int):
    """
    دکوریتور برای bypass کردن rate limit برای ادمین
    
    مثال:
        @bypass_rate_limit_for_admin(ADMIN_ID)
        @rate_limit(10, 10)
        async def my_handler(update, context):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # اگر ادمین بود، بدون چک rate limit اجرا کن
            if is_admin(user_id, admin_id):
                return await func(update, context, *args, **kwargs)
            
            # در غیر اینصورت، تابع اصلی (که rate limit داره) اجرا میشه
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# ==================== مثال استفاده ====================

"""
# در فایل user.py:

from rate_limiter import rate_limit, action_limit

@rate_limit(max_requests=10, window_seconds=10)
async def handle_text_messages(update: Update, context):
    # ...
    pass

@action_limit('order', max_requests=3, window_seconds=3600)
async def finalize_order_start(update: Update, context):
    # ...
    pass

@action_limit('discount', max_requests=5, window_seconds=60)
async def apply_discount_start(update: Update, context):
    # ...
    pass

@action_limit('cart', max_requests=20, window_seconds=60)
async def handle_pack_selection(update: Update, context):
    # ...
    pass
"""
