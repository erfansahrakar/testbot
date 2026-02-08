"""
توابع کمکی و Helper Functions
✅ Safe message editing
✅ Error handling wrappers
✅ Utility functions
"""
import logging
import asyncio
from typing import Optional, Union
from telegram import Message, InlineKeyboardMarkup
from telegram.error import BadRequest, TelegramError

logger = logging.getLogger(__name__)


async def safe_edit_message(
    message: Message,
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    max_retries: int = 3
) -> bool:
    """
    ویرایش ایمن پیام با retry
    
    Args:
        message: پیام برای ویرایش
        text: متن جدید
        parse_mode: نوع parse (Markdown, HTML)
        reply_markup: کیبورد (فقط InlineKeyboardMarkup)
        max_retries: تعداد تلاش مجدد
    
    Returns:
        True اگه موفق بود، False در غیر این صورت
    """
    for attempt in range(max_retries):
        try:
            await message.edit_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
        
        except BadRequest as e:
            error_msg = str(e).lower()
            
            # اگه پیام تغییر نکرده، مشکلی نیست
            if "message is not modified" in error_msg:
                logger.debug("Message was not modified (same content)")
                return True
            
            # اگه پیام حذف شده یا پیدا نشد
            if "message to edit not found" in error_msg or "message can't be edited" in error_msg:
                logger.warning(f"Cannot edit message: {e}")
                return False
            
            # خطاهای دیگه
            logger.error(f"BadRequest while editing message: {e}")
            return False
        
        except TelegramError as e:
            logger.warning(
                f"⚠️ Failed to edit message (attempt {attempt + 1}/{max_retries}): {e}"
            )
            
            if attempt == max_retries - 1:
                logger.error(f"❌ All attempts failed to edit message")
                return False
            
            # تاخیر با exponential backoff
            await asyncio.sleep(0.5 * (attempt + 1))
    
    return False


async def safe_send_message(
    context,
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup = None,
    max_retries: int = 3
) -> Optional[Message]:
    """
    ارسال ایمن پیام با retry
    
    Returns:
        Message object اگه موفق بود، None در غیر این صورت
    """
    for attempt in range(max_retries):
        try:
            return await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        
        except TelegramError as e:
            logger.warning(
                f"⚠️ Failed to send message (attempt {attempt + 1}/{max_retries}): {e}"
            )
            
            if attempt == max_retries - 1:
                logger.error(f"❌ All attempts failed to send message")
                return None
            
            await asyncio.sleep(0.5 * (attempt + 1))
    
    return None


async def safe_delete_message(
    context,
    chat_id: int,
    message_id: int,
    max_retries: int = 2
) -> bool:
    """
    حذف ایمن پیام
    
    Returns:
        True اگه موفق بود یا پیام قبلاً حذف شده بود
    """
    for attempt in range(max_retries):
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
            return True
        
        except BadRequest as e:
            error_msg = str(e).lower()
            
            # اگه پیام قبلاً حذف شده
            if "message to delete not found" in error_msg:
                logger.debug("Message already deleted")
                return True
            
            logger.warning(f"Cannot delete message: {e}")
            return False
        
        except TelegramError as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to delete message: {e}")
                return False
            
            await asyncio.sleep(0.2 * (attempt + 1))
    
    return False


def format_price(price: Union[int, float]) -> str:
    """
    فرمت کردن قیمت با جداکننده هزارگان
    
    Args:
        price: قیمت به تومان
    
    Returns:
        قیمت فرمت شده (مثلاً: "1,234,567")
    """
    return f"{int(price):,}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    کوتاه کردن متن با اضافه کردن ...
    
    Args:
        text: متن اصلی
        max_length: حداکثر طول
        suffix: پسوند (پیش‌فرض: ...)
    
    Returns:
        متن کوتاه شده
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """
    پاکسازی نام فایل از کاراکترهای نامعتبر
    
    Args:
        filename: نام فایل
    
    Returns:
        نام فایل پاکسازی شده
    """
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    return filename


def get_pagination_text(current_page: int, total_pages: int, total_items: int) -> str:
    """
    متن pagination
    
    Returns:
        مثلاً: "صفحه 1 از 5 (50 مورد)"
    """
    return f"صفحه {current_page} از {total_pages} ({total_items} مورد)"


async def answer_callback_safe(query, text: str = None, show_alert: bool = False) -> bool:
    """
    پاسخ ایمن به callback query
    
    Returns:
        True اگه موفق بود
    """
    try:
        await query.answer(text=text, show_alert=show_alert)
        return True
    except TelegramError as e:
        logger.warning(f"Failed to answer callback: {e}")
        return False


def chunk_list(lst: list, chunk_size: int):
    """
    تقسیم لیست به قسمت‌های کوچکتر
    
    Args:
        lst: لیست اصلی
        chunk_size: اندازه هر قسمت
    
    Yields:
        قسمت‌های لیست
    
    Example:
        >>> list(chunk_list([1,2,3,4,5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]
