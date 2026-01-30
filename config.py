"""
تنظیمات اصلی ربات
🔒 امن شده با Environment Variables
✅ FIX: Centralized Constants - همه stringها در یک جا
✅ FIX: Button Texts جمع شده
✅ FIX: Status Strings به یک جا منتقل شده
"""
import os
import warnings
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

# دریافت متغیر با مقدار پیش‌فرض
def get_env(key: str, default=None, required=True):
    """
    دریافت متغیر محیطی
    
    Args:
        key: نام متغیر
        default: مقدار پیش‌فرض
        required: آیا الزامی است؟
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(f"❌ متغیر محیطی {key} تنظیم نشده است!")
    
    return value


# ==================== Bot Configuration ====================

# توکن ربات - از BotFather دریافت کنید
BOT_TOKEN = get_env('BOT_TOKEN', required=True)

# آیدی عددی ادمین - از @userinfobot دریافت کنید
ADMIN_ID = int(get_env('ADMIN_ID', required=True))

# username کانال بدون @ - مثال: mychannel
CHANNEL_USERNAME = get_env('CHANNEL_USERNAME', required=True)


# ==================== Database Configuration ====================

# تنظیمات دیتابیس
DATABASE_NAME = get_env('DATABASE_NAME', default='shop_bot.db', required=False)

# مسیر ذخیره بکاپ‌ها
BACKUP_FOLDER = get_env('BACKUP_FOLDER', default='backups', required=False)

# ساعت بکاپ روزانه (فرمت 24 ساعته)
BACKUP_HOUR = int(get_env('BACKUP_HOUR', default='3', required=False))
BACKUP_MINUTE = int(get_env('BACKUP_MINUTE', default='0', required=False))


# ==================== Payment Configuration ====================

# شماره کارت برای پرداخت
CARD_NUMBER = get_env('CARD_NUMBER', required=True)
CARD_HOLDER = get_env('CARD_HOLDER', required=True)
IBAN_NUMBER = get_env('IBAN_NUMBER', required=True)


# ==================== Optional Configuration ====================

# مسیر لاگ‌ها
LOG_FOLDER = get_env('LOG_FOLDER', default='logs', required=False)

# سطح لاگ
LOG_LEVEL = get_env('LOG_LEVEL', default='INFO', required=False)

# زمان کش inline queries (ثانیه)
INLINE_CACHE_TIME = int(get_env('INLINE_CACHE_TIME', default='300', required=False))


# ==================== ✅ NEW: Button Texts ====================

# متن دکمه‌های منوی کاربر
BUTTON_TEXTS = {
    # User Menu
    'CART': '🛒 سبد خرید',
    'MY_ORDERS': '📦 سفارشات من',
    'MY_ADDRESS': '📍 آدرس ثبت شده من',
    'CONTACT_US': '📞 تماس با ما',
    'HELP': 'ℹ️ راهنما',
    
    # Admin Menu
    'DASHBOARD': '🎛 داشبورد',
    'STATS': '📊 آمار',
    'ADD_PRODUCT': '➕ افزودن محصول',
    'LIST_PRODUCTS': '📦 لیست محصولات',
    'PENDING_ORDERS': '📋 سفارشات جدید',
    'PAYMENT_CONFIRM': '💳 تایید پرداخت‌ها',
    'MANAGE_DISCOUNTS': '🎁 مدیریت تخفیف‌ها',
    'BROADCAST': '📢 پیام همگانی',
    'ANALYTICS': '📈 گزارش‌های تحلیلی',
    'BACKUP': '💾 بکاپ دستی',
    'CLEANUP': '🧹 پاکسازی دیتابیس',
    
    # Common
    'CANCEL': '❌ لغو',
    'BACK': '🔙 بازگشت',
}


# ==================== ✅ NEW: Shipping Methods ====================

SHIPPING_METHODS = {
    'terminal': {
        'name': 'ترمینال',
        'emoji': '🚌',
        'display': 'ترمینال 🚌'
    },
    'barbari': {
        'name': 'باربری',
        'emoji': '🚚',
        'display': 'باربری 🚚'
    },
    'tipax': {
        'name': 'تیپاکس',
        'emoji': '📦',
        'display': 'تیپاکس 📦'
    },
    'chapar': {
        'name': 'چاپار',
        'emoji': '🏃',
        'display': 'چاپار 🏃'
    }
}


# ==================== ✅ NEW: Order Status Display ====================

ORDER_STATUS_EMOJI = {
    'pending': '⏳',
    'waiting_payment': '💳',
    'receipt_sent': '📤',
    'payment_confirmed': '✅',
    'confirmed': '✅',
    'rejected': '❌',
    'expired': '⏰'
}

ORDER_STATUS_TEXT = {
    'pending': 'در انتظار تایید',
    'waiting_payment': 'در انتظار پرداخت',
    'receipt_sent': 'رسید ارسال شده',
    'payment_confirmed': 'تایید شده',
    'confirmed': 'تایید شده',
    'rejected': 'رد شده',
    'expired': 'منقضی شده'
}


# ==================== Messages ====================

# پیام‌های سیستم
MESSAGES = {
    "start_user": "🛍 به فروشگاه مانتو ما خوش اومدید!\n\n✨ محصولات جدید رو در کانال ما ببینید:\n📢 @manto_omdeh_erfan\n\nو مستقیماً از همون‌جا سفارش بدید!\n\n📦 سبد خرید شما خالیه.",
    "start_admin": "👨‍💼 پنل مدیریت\n\nبرای شروع از منوی زیر استفاده کنید.",
    "product_added": "✅ محصول با موفقیت اضافه شد!",
    "pack_added": "✅ پک به محصول اضافه شد!",
    "order_received": "📦 سفارش شما ثبت شد!\n\nلطفاً منتظر تایید ادمین باشید.",
    "order_confirmed": "✅ سفارش شما تایید شد!\n\n💳 لطفاً مبلغ {amount} تومان را به شماره کارت زیر واریز کنید:\n\n{card}\n\n{iban}\n\nبه نام: {holder}\n\n📷 بعد از واریز، رسید را ارسال کنید.\n\n⏰ سفارش شما تا یک ساعت برای پرداخت فعال می‌باشد و بعد از یک ساعت سفارش لغو خواهد شد.",
    "order_rejected": "❌ متأسفانه سفارش شما رد شد.",
    "receipt_received": "✅ رسید شما دریافت شد!\n\nلطفاً منتظر تایید نهایی باشید.",
    "payment_confirmed": "✅ پرداخت شما تایید شد!\n\n🎉 سفارش شما در حال آماده‌سازی است.",
    "payment_rejected": "❌ رسید شما رد شد. لطفاً دوباره تلاش کنید.",
    
    # ✅ NEW: پیام‌های اضافی
    "cart_empty": "🛒 سبد خرید شما خالی است!",
    "order_expired": "⏰ این سفارش منقضی شده است!\n\n💡 می‌توانید آن را حذف کنید و سفارش جدیدی ثبت کنید.",
    "no_orders": "📭 شما هنوز سفارشی ثبت نکرده‌اید.",
    "discount_applied": "✅ کد تخفیف اعمال شد!",
    "discount_invalid": "❌ کد تخفیف نامعتبر است!",
    "discount_expired": "❌ این کد تخفیف منقضی شده است!",
    "discount_limit_reached": "❌ این کد تخفیف به حداکثر تعداد استفاده رسیده است!",
}


# ==================== ✅ NEW: Contact Info ====================

CONTACT_INFO = {
    "phone": "09123834869",
    "telegram_id": "@manto_omde_erfan",
    "channel": "@manto_omdeh_erfan",
    "support_hours": "همه روزه ۹ صبح تا ۹ شب"
}


# ==================== ✅ NEW: Limits & Constraints ====================

LIMITS = {
    # Rate Limits
    'RATE_LIMIT_REQUESTS': 20,
    'RATE_LIMIT_WINDOW': 60,  # seconds
    
    # Order Limits
    'MAX_ORDERS_PER_HOUR': 3,
    'ORDER_EXPIRY_HOURS': 1,  # ۱ ساعت برای پرداخت
    
    # Discount Limits
    'MAX_DISCOUNT_ATTEMPTS': 5,
    'DISCOUNT_ATTEMPT_WINDOW': 60,  # seconds
    
    # Validation Limits
    'MAX_PRODUCT_NAME_LENGTH': 100,
    'MAX_PACK_NAME_LENGTH': 50,
    'MAX_ADDRESS_LENGTH': 500,
    'MIN_ADDRESS_LENGTH': 10,
    'MAX_PRICE': 100_000_000,  # 100 میلیون تومان
    'MAX_QUANTITY': 10_000,
}


# ==================== ✅ NEW: Helper Functions ====================

def get_button_text(key: str) -> str:
    """
    دریافت متن دکمه
    
    Args:
        key: کلید دکمه
        
    Returns:
        متن دکمه یا خود کلید اگه پیدا نشد
    """
    return BUTTON_TEXTS.get(key, key)


def get_shipping_display(method: str) -> str:
    """
    دریافت نمایش نحوه ارسال
    
    Args:
        method: نوع ارسال (terminal, barbari, etc.)
        
    Returns:
        نمایش کامل با ایموجی
    """
    return SHIPPING_METHODS.get(method, {}).get('display', method)


def get_order_status_display(status: str) -> tuple:
    """
    دریافت ایموجی و متن وضعیت سفارش
    
    Args:
        status: وضعیت سفارش
        
    Returns:
        (emoji, text)
    """
    emoji = ORDER_STATUS_EMOJI.get(status, '❓')
    text = ORDER_STATUS_TEXT.get(status, 'نامشخص')
    return emoji, text


def format_contact_info() -> str:
    """
    فرمت کردن اطلاعات تماس
    
    Returns:
        متن فرمت شده اطلاعات تماس
    """
    return (
        f"📞 <b>راه‌های ارتباطی با ما:</b>\n\n"
        f"📱 شماره تماس: <code>{CONTACT_INFO['phone']}</code>\n"
        f"🆔 آیدی تلگرام: {CONTACT_INFO['telegram_id']}\n"
        f"📢 کانال ما: {CONTACT_INFO['channel']}\n\n"
        f"🕐 پاسخگویی: {CONTACT_INFO['support_hours']}"
    )


# ==================== Validation ====================

def validate_config():
    """اعتبارسنجی تنظیمات"""
    errors = []
    
    # بررسی توکن
    if not BOT_TOKEN or len(BOT_TOKEN) < 20:
        errors.append("❌ توکن ربات نامعتبر است")
    
    # بررسی ADMIN_ID
    if ADMIN_ID <= 0:
        errors.append("❌ ADMIN_ID نامعتبر است")
    
    # بررسی شماره کارت
    if not CARD_NUMBER or len(CARD_NUMBER) != 16:
        errors.append("⚠️ شماره کارت ممکن است نامعتبر باشد")
    
    # بررسی کانال
    if not CHANNEL_USERNAME:
        errors.append("⚠️ username کانال تنظیم نشده است")
    
    if errors:
        print("\n" + "="*50)
        print("⚠️  خطاهای تنظیمات:")
        for error in errors:
            print(f"  {error}")
        print("="*50 + "\n")
        
        if any("❌" in e for e in errors):
            error_msg = "تنظیمات اشتباه است!"
            warnings.warn(f"⚠️ Configuration issue: {error_msg}")
        return False
    else:
        print("✅ تمام تنظیمات معتبر هستند")
        return True


# اجرای اعتبارسنجی
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        warnings.warn(f"⚠️ Configuration issue: {e}")
        print(f"\n⚠️ هشدار تنظیمات: {e}\n")
        print("💡 راهنما:")
        print("  1. فایل .env را در روت پروژه ایجاد کنید")
        print("  2. از .env.example به عنوان الگو استفاده کنید")
        print("  3. تمام متغیرهای الزامی را تنظیم کنید\n")


# ==================== Debug Mode ====================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("📋 تنظیمات ربات:")
    print("="*50)
    print(f"✅ BOT_TOKEN: {'*' * 20}...{BOT_TOKEN[-10:] if BOT_TOKEN else 'NOT SET'}")
    print(f"✅ ADMIN_ID: {ADMIN_ID}")
    print(f"✅ CHANNEL: @{CHANNEL_USERNAME}")
    print(f"✅ DATABASE: {DATABASE_NAME}")
    print(f"✅ BACKUP_FOLDER: {BACKUP_FOLDER}")
    print(f"✅ CARD: {CARD_NUMBER[:4]}****{CARD_NUMBER[-4:] if len(CARD_NUMBER) >= 8 else '****'}")
    print(f"✅ CARD_HOLDER: {CARD_HOLDER}")
    print(f"✅ BACKUP_TIME: {BACKUP_HOUR:02d}:{BACKUP_MINUTE:02d}")
    print("="*50 + "\n")
    
    # نمایش Constants
    print("📦 Constants:")
    print(f"  - Button Texts: {len(BUTTON_TEXTS)} دکمه")
    print(f"  - Shipping Methods: {len(SHIPPING_METHODS)} روش")
    print(f"  - Order Statuses: {len(ORDER_STATUS_TEXT)} وضعیت")
    print(f"  - Messages: {len(MESSAGES)} پیام")
    print(f"  - Limits: {len(LIMITS)} محدودیت")
    print("\n")
    
    validate_config()
