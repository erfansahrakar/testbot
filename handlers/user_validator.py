"""
ابزارهای کمکی برای چک کردن وجود effective_user
"""
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def require_user(func):
    """
    دکوراتور برای چک کردن وجود effective_user
    
    اگر effective_user وجود نداشته باشد، لاگ می‌کند و از ادامه کار جلوگیری می‌کند
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # چک کردن وجود effective_user
        if not update.effective_user:
            logger.warning(f"⚠️ {func.__name__} فراخوانی شد اما effective_user وجود ندارد")
            
            # اگر query باشد، پاسخ بده
            if update.callback_query:
                try:
                    await update.callback_query.answer(
                        "❌ خطا در شناسایی کاربر!",
                        show_alert=True
                    )
                except Exception as e:
                    logger.error(f"خطا در پاسخ به callback_query: {e}")
            
            # اگر message باشد، پاسخ بده
            elif update.message:
                try:
                    await update.message.reply_text("❌ خطا در شناسایی کاربر!")
                except Exception as e:
                    logger.error(f"خطا در پاسخ به message: {e}")
            
            return None
        
        # اگر همه چیز اوکی بود، تابع اصلی رو اجرا کن
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def get_user_id(update: Update) -> int | None:
    """
    دریافت ایمن user_id از update
    
    Returns:
        int | None: user_id یا None اگر وجود نداشت
    """
    if not update.effective_user:
        logger.warning("⚠️ تلاش برای دریافت user_id اما effective_user وجود ندارد")
        return None
    
    return update.effective_user.id
