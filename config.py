"""
تنظیمات اصلی ربات
🔒 امن شده با Environment Variables
✅ FIX باگ 8: Config Validation بدون crash - فقط warning میده
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


# ==================== Optional Configuration ====================

# مسیر لاگ‌ها
LOG_FOLDER = get_env('LOG_FOLDER', default='logs', required=False)

# سطح لاگ
LOG_LEVEL = get_env('LOG_LEVEL', default='INFO', required=False)

# زمان کش inline queries (ثانیه)
INLINE_CACHE_TIME = int(get_env('INLINE_CACHE_TIME', default='300', required=False))


# ==================== Messages ====================

# پیام‌های سیستم
MESSAGES = {
    "start_user": "🛍 به فروشگاه مانتو ما خوش اومدید!\n\n✨ محصولات جدید رو در کانال ما ببینید:\n📢 @manto_omdeh_erfan\n\nو مستقیماً از همون‌جا سفارش بدید!\n\n📦 سبد خرید شما خالیه.",
    "start_admin": "👨‍💼 پنل مدیریت\n\nبرای شروع از منوی زیر استفاده کنید.",
    "product_added": "✅ محصول با موفقیت اضافه شد!",
    "pack_added": "✅ پک به محصول اضافه شد!",
    "order_received": "📦 سفارش شما ثبت شد!\n\nلطفاً منتظر تایید ادمین باشید.",
    "order_confirmed": "✅ سفارش شما تایید شد!\n\n💳 لطفاً مبلغ {amount} تومان را به شماره کارت زیر واریز کنید:\n\n{card}\n\nبه نام: {holder}\n\n📷 بعد از واریز، رسید را ارسال کنید.",
    "order_rejected": "❌ متأسفانه سفارش شما رد شد.",
    "receipt_received": "✅ رسید شما دریافت شد!\n\nلطفاً منتظر تایید نهایی باشید.",
    "payment_confirmed": "✅ پرداخت شما تایید شد!\n\n🎉 سفارش شما در حال آماده‌سازی است.",
    "payment_rejected": "❌ رسید شما رد شد. لطفاً دوباره تلاش کنید.",
}


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
        
        # ✅ FIX باگ 8: فقط warning بده، crash نکن
        if any("❌" in e for e in errors):
            error_msg = "تنظیمات اشتباه است!"
            warnings.warn(f"⚠️ Configuration issue: {error_msg}")
            # بجای raise، فقط warning میدیم
        return False
    else:
        print("✅ تمام تنظیمات معتبر هستند")
        return True


# ✅ FIX باگ 8: اجرای اعتبارسنجی با warning به جای crash
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        # ✅ FIX: فقط warning، crash نمی‌کنیم
        warnings.warn(f"⚠️ Configuration issue: {e}")
        print(f"\n⚠️ هشدار تنظیمات: {e}\n")
        print("💡 راهنما:")
        print("  1. فایل .env را در روت پروژه ایجاد کنید")
        print("  2. از .env.example به عنوان الگو استفاده کنید")
        print("  3. تمام متغیرهای الزامی را تنظیم کنید\n")


# ==================== Debug Mode ====================

# نمایش تنظیمات (بدون اطلاعات حساس)
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
    
    validate_config()
