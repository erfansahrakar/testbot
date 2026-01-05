"""
سیستم مدیریت پیشرفته خطاها
✅ لاگ دقیق با context
✅ Retry mechanism
✅ اطلاع‌رسانی به ادمین
✅ ذخیره خطاها
"""
import logging
import asyncio
import traceback
import functools
from datetime import datetime
from typing import Callable, Optional, Any, Dict
from telegram.ext import ContextTypes
from telegram.error import TelegramError, NetworkError, TimedOut, BadRequest
from config import ADMIN_ID

logger = logging.getLogger(__name__)


class ErrorCategory:
    """دسته‌بندی خطاها"""
    DATABASE = "database"
    NETWORK = "network"
    TELEGRAM = "telegram"
    VALIDATION = "validation"
    BUSINESS = "business"
    UNKNOWN = "unknown"


class ErrorSeverity:
    """شدت خطا"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BotError(Exception):
    """کلاس پایه برای خطاهای سفارشی ربات"""
    def __init__(self, message: str, category: str = ErrorCategory.UNKNOWN, 
                 severity: str = ErrorSeverity.MEDIUM, context: Optional[Dict] = None):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)


class DatabaseError(BotError):
    """خطای دیتابیس"""
    def __init__(self, message: str, context: Optional[Dict] = None):
        super().__init__(message, ErrorCategory.DATABASE, ErrorSeverity.HIGH, context)


class EnhancedErrorHandler:
    """مدیریت پیشرفته خطاها"""
    
    def __init__(self, health_checker=None):
        self.health_checker = health_checker
        self.error_counts = {}
        self.last_notification = {}
        self.notification_cooldown = 300  # 5 دقیقه
    
    async def handle_error(self, error: Exception, context: ContextTypes.DEFAULT_TYPE, 
                          user_id: Optional[int] = None, extra_info: Optional[Dict] = None):
        """مدیریت مرکزی خطاها"""
        
        error_info = self._extract_error_info(error, user_id, extra_info)
        self._log_error(error_info)
        
        if self.health_checker:
            self.health_checker.add_error(
                error_type=error_info['category'],
                error_message=error_info['message'],
                user_id=user_id
            )
        
        self._count_error(error_info['category'])
        await self._notify_admin_if_needed(context, error_info)
        
        return self._get_user_message(error_info)
    
    def _extract_error_info(self, error: Exception, user_id: Optional[int], 
                           extra_info: Optional[Dict]) -> Dict:
        """استخراج اطلاعات کامل خطا"""
        
        if isinstance(error, BotError):
            category = error.category
            severity = error.severity
            message = error.message
            context = error.context
        elif isinstance(error, TelegramError):
            category = ErrorCategory.TELEGRAM
            severity = ErrorSeverity.MEDIUM
            message = str(error)
            context = {}
        elif isinstance(error, (IOError, OSError)):
            category = ErrorCategory.DATABASE
            severity = ErrorSeverity.HIGH
            message = str(error)
            context = {}
        else:
            category = ErrorCategory.UNKNOWN
            severity = ErrorSeverity.MEDIUM
            message = str(error)
            context = {}
        
        return {
            'type': type(error).__name__,
            'category': category,
            'severity': severity,
            'message': message,
            'traceback': traceback.format_exc(),
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'context': context,
            'extra_info': extra_info or {}
        }
    
    def _log_error(self, error_info: Dict):
        """لاگ کردن خطا با جزئیات"""
        severity = error_info['severity']
        
        log_message = (
            f"{'='*50}\n"
            f"❌ خطا رخ داد!\n"
            f"نوع: {error_info['type']}\n"
            f"دسته: {error_info['category']}\n"
            f"شدت: {severity}\n"
            f"پیام: {error_info['message']}\n"
        )
        
        if error_info['user_id']:
            log_message += f"کاربر: {error_info['user_id']}\n"
        
        if error_info['context']:
            log_message += f"Context: {error_info['context']}\n"
        
        log_message += f"{'='*50}\n"
        log_message += f"Traceback:\n{error_info['traceback']}"
        
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def _count_error(self, category: str):
        """شمارش خطاها"""
        if category not in self.error_counts:
            self.error_counts[category] = 0
        self.error_counts[category] += 1
    
    async def _notify_admin_if_needed(self, context: ContextTypes.DEFAULT_TYPE, error_info: Dict):
        """اطلاع‌رسانی به ادمین"""
        severity = error_info['severity']
        category = error_info['category']
        
        if severity not in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            return
        
        now = datetime.now().timestamp()
        last_time = self.last_notification.get(category, 0)
        
        if now - last_time < self.notification_cooldown:
            return
        
        self.last_notification[category] = now
        
        severity_emoji = {
            ErrorSeverity.CRITICAL: '🔴',
            ErrorSeverity.HIGH: '🟠',
            ErrorSeverity.MEDIUM: '🟡',
            ErrorSeverity.LOW: '🟢'
        }
        
        emoji = severity_emoji.get(severity, '⚠️')
        
        message = f"{emoji} **خطای {severity.upper()}**\n\n"
        message += f"**دسته:** {category}\n"
        message += f"**نوع:** {error_info['type']}\n"
        message += f"**پیام:** {error_info['message'][:200]}\n"
        
        if error_info['user_id']:
            message += f"**کاربر:** {error_info['user_id']}\n"
        
        message += f"\n**زمان:** {error_info['timestamp'][:19]}\n"
        
        count = self.error_counts.get(category, 0)
        if count > 1:
            message += f"\n⚠️ این خطا {count} بار تکرار شده است!"
        
        try:
            await context.bot.send_message(ADMIN_ID, message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    
    def _get_user_message(self, error_info: Dict) -> str:
        """پیام مناسب برای کاربر"""
        category = error_info['category']
        
        messages = {
            ErrorCategory.DATABASE: (
                "❌ مشکلی در ذخیره‌سازی اطلاعات پیش آمد.\n"
                "لطفاً چند لحظه صبر کنید و دوباره تلاش کنید."
            ),
            ErrorCategory.NETWORK: (
                "❌ مشکل در ارتباط با سرور.\n"
                "لطفاً اتصال اینترنت خود را بررسی کنید."
            ),
            ErrorCategory.TELEGRAM: (
                "❌ مشکلی در ارسال پیام پیش آمد.\n"
                "لطفاً دوباره تلاش کنید."
            ),
            ErrorCategory.VALIDATION: (
                "❌ اطلاعات وارد شده نامعتبر است.\n"
                "لطفاً دوباره بررسی کنید."
            ),
            ErrorCategory.BUSINESS: (
                "❌ عملیات قابل انجام نیست.\n"
                f"دلیل: {error_info['message']}"
            ),
            ErrorCategory.UNKNOWN: (
                "❌ خطای غیرمنتظره‌ای رخ داد.\n"
                "لطفاً با پشتیبانی تماس بگیرید."
            )
        }
        
        return messages.get(category, messages[ErrorCategory.UNKNOWN])
    
    def get_error_stats(self) -> Dict:
        """آمار خطاها"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'by_category': self.error_counts.copy()
        }


# ==================== Decorators ====================

def retry_on_error(max_retries: int = 3, delay: float = 1.0, exponential_backoff: bool = True):
    """Decorator برای retry خودکار"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if isinstance(e, (BadRequest,)):
                        raise
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠️ Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}"
                        )
                        await asyncio.sleep(current_delay)
                        
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        logger.error(
                            f"❌ All {max_retries} attempts failed for {func.__name__}"
                        )
            
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if isinstance(e, (BadRequest,)):
                        raise
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠️ Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}"
                        )
                        import time
                        time.sleep(current_delay)
                        
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        logger.error(
                            f"❌ All {max_retries} attempts failed for {func.__name__}"
                        )
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def handle_errors(error_handler: EnhancedErrorHandler):
    """Decorator برای مدیریت خطاها"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                user_id = update.effective_user.id if update.effective_user else None
                
                error_message = await error_handler.handle_error(
                    error=e,
                    context=context,
                    user_id=user_id,
                    extra_info={'function': func.__name__}
                )
                
                try:
                    if update.message:
                        await update.message.reply_text(error_message)
                    elif update.callback_query:
                        await update.callback_query.answer("❌ خطا رخ داد!", show_alert=True)
                except:
                    pass
                
                return None
        
        return wrapper
    return decorator
