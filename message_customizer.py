"""
✅ FEATURE #5: سفارشی‌سازی پیام‌های ربات (سینک شده با فایل‌های جدید)
ادمین می‌تونه متن پیام‌های بات رو تغییر بده
"""
import json
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID

logger = logging.getLogger(__name__)

# States
EDIT_MESSAGE = 1

# فایل ذخیره پیام‌های سفارشی
CUSTOM_MESSAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_messages.json")

# ✅ پیام‌های پیش‌فرض (دقیقاً مطابق با config.py و استفاده واقعی)
DEFAULT_MESSAGES = {
    # ========== پیام‌های اصلی که در کد استفاده میشن ==========
    
    # پیام‌های شروع
    "start_user": "👋 سلام {name}!\n\n🛍 به فروشگاه ما خوش آمدید.\n\nلطفاً از منوی زیر استفاده کنید:",
    "start_admin": "👨‍💼 پنل مدیریت\n\nبرای شروع از منوی زیر استفاده کنید.",
    
    # پیام‌های محصول (استفاده میشن)
    "product_added": "✅ محصول با موفقیت اضافه شد!",
    "pack_added": "✅ پک به محصول اضافه شد!",
    
    # پیام‌های سفارش (استفاده میشن)
    "order_received": "📦 سفارش شما ثبت شد!\n\nلطفاً منتظر تایید ادمین باشید.",
    "order_confirmed": "✅ سفارش شما تایید شد!\n\n💳 لطفاً مبلغ {amount} تومان را به شماره کارت زیر واریز کنید:\n\n{card}\n\n{iban}\n\nبه نام: {holder}\n\n📷 بعد از واریز، رسید را ارسال کنید.\n\n⏰ سفارش شما تا یک ساعت برای پرداخت فعال می‌باشد و بعد از یک ساعت سفارش لغو خواهد شد.",
    "order_rejected": "❌ متأسفانه سفارش شما رد شد.",
    
    # پیام‌های پرداخت (استفاده میشن)
    "receipt_received": "✅ رسید شما دریافت شد!\n\nلطفاً منتظر تایید نهایی باشید.",
    "payment_confirmed": "✅ پرداخت شما تایید شد!\n\n🎉 سفارش شما در حال آماده‌سازی است.",
    "payment_rejected": "❌ رسید شما رد شد. لطفاً دوباره تلاش کنید.",
    
    # ========== پیام‌های اضافی (ممکنه استفاده بشن) ==========
    
    # محصولات
    "product_not_found": "❌ محصول یافت نشد.",
    "product_unavailable": "❌ این محصول فعلاً موجود نیست.",
    "product_deleted": "✅ محصول حذف شد.",
    
    # سبد خرید
    "cart_empty": "🛒 سبد خرید شما خالی است!",
    "cart_cleared": "✅ سبد خرید شما خالی شد.",
    "added_to_cart": "✅ به سبد خرید اضافه شد!",
    "removed_from_cart": "🗑 از سبد خرید حذف شد!",
    "cart_error": "❌ خطا در بروزرسانی سبد!",
    
    # سفارشات
    "order_shipped": "📦 سفارش شما ارسال شد!\n\n🚚 کد رهگیری: {tracking_code}",
    "order_cancelled": "❌ سفارش شما لغو شد.",
    "order_expired": "⏰ این سفارش منقضی شده است!\n\n💡 می‌توانید آن را حذف کنید و سفارش جدیدی ثبت کنید.",
    "no_orders": "📭 شما هنوز سفارشی ثبت نکرده‌اید.",
    "order_details_confirmed": "✅ اطلاعات تایید شد",
    
    # پرداخت
    "payment_waiting": "💳 لطفاً رسید پرداخت خود را ارسال کنید.\n\n⏰ زمان باقی‌مانده: {minutes} دقیقه",
    "no_pending_receipts": "📭 رسید پرداختی برای تایید وجود ندارد.",
    "no_pending_payments": "شما سفارش در انتظار پرداختی ندارید.",
    
    # تخفیف
    "discount_applied": "✅ کد تخفیف اعمال شد!\n\n💰 مبلغ تخفیف: {amount} تومان",
    "discount_invalid": "❌ کد تخفیف نامعتبر است!",
    "discount_expired": "❌ این کد تخفیف منقضی شده است!",
    "discount_limit_reached": "❌ این کد تخفیف به حداکثر تعداد استفاده رسیده است!",
    "discount_min_purchase": "❌ حداقل خرید برای این کد: {amount} تومان",
    "discount_already_used": "❌ شما قبلاً از این کد استفاده کرده‌اید!",
    "discount_removed": "🗑 کد تخفیف حذف شد.",
    
    # آدرس و اطلاعات
    "address_saved": "✅ آدرس شما ذخیره شد!",
    "address_required": "📍 لطفاً آدرس کامل خود را وارد کنید:",
    "phone_required": "📞 لطفاً شماره موبایل خود را وارد کنید:",
    "name_required": "👤 لطفاً نام و نام خانوادگی خود را وارد کنید:",
    "invalid_phone": "❌ شماره موبایل نامعتبر است! لطفاً یک شماره معتبر وارد کنید.",
    "invalid_name": "❌ نام وارد شده نامعتبر است!",
    "info_updated": "✅ اطلاعات شما به‌روزرسانی شد.",
    
    # خطاها
    "error_general": "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.",
    "error_network": "❌ خطا در اتصال! لطفاً بعداً تلاش کنید.",
    "error_database": "❌ خطا در دیتابیس! با پشتیبانی تماس بگیرید.",
    "error_order_submit": "❌ خطا در ثبت سفارش! لطفاً دوباره تلاش کنید.",
    
    # عمومی
    "success_general": "✅ عملیات با موفقیت انجام شد!",
    "cancelled": "❌ عملیات لغو شد.",
    "confirmed": "✅ تایید شد!",
    "welcome_back": "👋 خوش آمدید!\n\nچه کمکی می‌تونیم بکنیم؟",
    "thank_you": "🙏 از خرید شما سپاسگزاریم!",
    
    # راهنما
    "help_text": "📖 **راهنمای استفاده از ربات**\n\n1. محصولات را از کانال مشاهده کنید\n2. روی لینک محصول کلیک کنید\n3. به سبد خرید اضافه کنید\n4. سفارش خود را نهایی کنید\n5. رسید پرداخت را ارسال کنید",
    "contact_info": "📞 **تماس با ما**\n\n📱 شماره تماس: {phone}\n✈️ تلگرام: {telegram_id}\n📢 کانال: {channel}\n\n🕐 ساعات پاسخگویی: {support_hours}",
    
    # ادمین
    "admin_order_pending": "📋 سفارشات در انتظار تایید: {count} سفارش",
    "admin_no_pending_orders": "📭 سفارشی در انتظار تایید وجود ندارد.",
    "admin_receipts_pending": "💳 رسیدهای در انتظار تایید: {count} رسید",
    "admin_no_pending_receipts": "📭 رسید پرداختی برای تایید وجود ندارد.",
    "admin_orders_unshipped": "📦 سفارشات ارسال نشده: {count} سفارش",
    "admin_no_unshipped": "📭 سفارشی ارسال نشده وجود نداشت.",
    "admin_orders_shipped": "✅ سفارشات ارسال شده: {count} سفارش",
    "admin_no_shipped": "📭 سفارشی ارسال شده وجود نداشت.",
    
    # Broadcast
    "broadcast_started": "📢 پیام شما در حال ارسال به {count} کاربر است...",
    "broadcast_completed": "✅ پیام به {success} کاربر ارسال شد.\n❌ {failed} کاربر ناموفق.",
    "broadcast_cancelled": "❌ ارسال پیام لغو شد.",
}


class MessageCustomizer:
    """مدیریت سفارشی‌سازی پیام‌ها"""
    
    def __init__(self):
        self.custom_messages = self.load_custom_messages()
    
    def load_custom_messages(self):
        """بارگذاری پیام‌های سفارشی از فایل"""
        try:
            with open(CUSTOM_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.error(f"Error loading custom messages: {e}")
            return {}
    
    def save_custom_messages(self):
        """ذخیره پیام‌های سفارشی"""
        try:
            with open(CUSTOM_MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.custom_messages, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving custom messages: {e}")
            return False
    
    def get_message(self, key, **kwargs):
        """
        دریافت پیام (سفارشی یا پیش‌فرض)
        
        Args:
            key: کلید پیام
            **kwargs: متغیرهایی که باید جایگزین بشن
        
        Returns:
            str: متن پیام
        """
        # اول چک کن سفارشی داریم
        message = self.custom_messages.get(key)
        
        # اگه نداریم، از پیش‌فرض استفاده کن
        if not message:
            message = DEFAULT_MESSAGES.get(key, f"[پیام {key} پیدا نشد]")
        
        # جایگزینی متغیرها
        try:
            return message.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in message {key}: {e}")
            return message
        except Exception as e:
            logger.error(f"Error formatting message {key}: {e}")
            return message
    
    def set_message(self, key, value):
        """تنظیم پیام سفارشی"""
        self.custom_messages[key] = value
        return self.save_custom_messages()
    
    def reset_message(self, key):
        """بازگشت به پیام پیش‌فرض"""
        if key in self.custom_messages:
            del self.custom_messages[key]
            return self.save_custom_messages()
        return True
    
    def get_all_keys(self):
        """لیست تمام کلیدهای پیام"""
        return list(DEFAULT_MESSAGES.keys())
    
    def get_categories(self):
        """دسته‌بندی پیام‌ها"""
        categories = {
            "🏠 شروع و خوشامد": ["start_user", "start_admin", "welcome_back"],
            "📦 محصولات": ["product_added", "pack_added", "product_not_found", "product_unavailable", "product_deleted"],
            "🛒 سبد خرید": ["cart_empty", "cart_cleared", "added_to_cart", "removed_from_cart", "cart_error"],
            "📋 سفارشات": [
                "order_received", "order_confirmed", "order_rejected", "order_shipped",
                "order_cancelled", "order_expired", "no_orders", "order_details_confirmed"
            ],
            "💳 پرداخت": [
                "receipt_received", "payment_confirmed", "payment_rejected",
                "payment_waiting", "no_pending_receipts", "no_pending_payments"
            ],
            "🎁 تخفیف": [
                "discount_applied", "discount_invalid", "discount_expired",
                "discount_limit_reached", "discount_min_purchase", "discount_already_used", "discount_removed"
            ],
            "📍 آدرس": [
                "address_saved", "address_required", "phone_required", "name_required",
                "invalid_phone", "invalid_name", "info_updated"
            ],
            "❌ خطاها": ["error_general", "error_network", "error_database", "error_order_submit"],
            "✅ عمومی": ["success_general", "cancelled", "confirmed", "thank_you", "help_text", "contact_info"],
            "👨‍💼 پیام‌های ادمین": [
                "admin_order_pending", "admin_no_pending_orders", "admin_receipts_pending",
                "admin_no_pending_receipts", "admin_orders_unshipped", "admin_no_unshipped",
                "admin_orders_shipped", "admin_no_shipped"
            ],
            "📢 پیام همگانی": ["broadcast_started", "broadcast_completed", "broadcast_cancelled"],
        }
        return categories


# Instance global
message_customizer = MessageCustomizer()


# ==================== Handler Functions ====================

async def customize_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی سفارشی‌سازی پیام‌ها"""
    # Check message or callback
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if not message:
        return
    
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return
    
    categories = message_customizer.get_categories()
    
    keyboard = []
    for category_name in categories.keys():
        keyboard.append([
            InlineKeyboardButton(category_name, callback_data=f"msg_cat:{category_name}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_admin")])
    
    text = "⚙️ **سفارشی‌سازی پیام‌ها**\n\nیک دسته انتخاب کنید:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


async def show_category_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پیام‌های یک دسته"""
    query = update.callback_query
    await query.answer()
    
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return
    
    category_name = query.data.split(':', 1)[1]
    categories = message_customizer.get_categories()
    message_keys = categories.get(category_name, [])
    
    keyboard = []
    for key in message_keys:
        is_custom = key in message_customizer.custom_messages
        emoji = "✏️" if is_custom else "📝"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {key}",
                callback_data=f"msg_edit:{key}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="msg_back_to_categories")])
    
    await query.edit_message_text(
        f"⚙️ **{category_name}**\n\n"
        "📝 = پیش‌فرض | ✏️ = سفارشی شده\n\n"
        "برای ویرایش روی پیام کلیک کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_message_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پیش‌نمایش پیام"""
    query = update.callback_query
    await query.answer()
    
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return
    
    key = query.data.split(':')[1]
    
    current_message = message_customizer.get_message(key)
    is_custom = key in message_customizer.custom_messages
    default_message = DEFAULT_MESSAGES.get(key, "")
    
    text = f"📝 **ویرایش: `{key}`**\n\n"
    text += f"{'✏️ متن فعلی (سفارشی):' if is_custom else '📝 متن فعلی (پیش‌فرض):'}\n"
    text += f"```\n{current_message}\n```\n\n"
    
    if is_custom and default_message:
        text += f"📌 متن پیش‌فرض:\n```\n{default_message}\n```\n\n"
    
    text += "💡 متغیرها:\n"
    text += "`{name}` `{amount}` `{card}` `{iban}` `{holder}`\n"
    text += "`{tracking_code}` `{channel}` `{phone}` `{count}`"
    
    keyboard = [
        [InlineKeyboardButton("✏️ ویرایش", callback_data=f"msg_start_edit:{key}")],
    ]
    
    if is_custom:
        keyboard.append([InlineKeyboardButton("🔄 بازگشت به پیش‌فرض", callback_data=f"msg_reset:{key}")])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="msg_back_to_list")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def start_edit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش پیام"""
    query = update.callback_query
    await query.answer()
    
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    key = query.data.split(':')[1]
    context.user_data['editing_message_key'] = key
    
    await query.edit_message_text(
        f"✏️ **ویرایش: `{key}`**\n\n"
        "لطفاً متن جدید را ارسال کنید.\n\n"
        "💡 متغیرها: `{{name}}` `{{amount}}` `{{card}}` ...\n\n"
        "لغو: /cancel",
        parse_mode='Markdown'
    )
    
    return EDIT_MESSAGE


async def receive_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن جدید"""
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    key = context.user_data.get('editing_message_key')
    if not key:
        await update.message.reply_text("❌ خطا! دوباره تلاش کنید.")
        return ConversationHandler.END
    
    new_message = update.message.text
    
    if message_customizer.set_message(key, new_message):
        await update.message.reply_text(
            f"✅ پیام `{key}` به‌روز شد!\n\n```\n{new_message}\n```",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ خطا در ذخیره!")
    
    context.user_data.pop('editing_message_key', None)
    return ConversationHandler.END


async def reset_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به پیش‌فرض"""
    query = update.callback_query
    await query.answer()
    
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return
    
    key = query.data.split(':')[1]
    
    if message_customizer.reset_message(key):
        default_message = DEFAULT_MESSAGES.get(key, "")
        await query.edit_message_text(
            f"✅ `{key}` به پیش‌فرض بازگشت!\n\n```\n{default_message}\n```",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ خطا!")


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ویرایش"""
    context.user_data.pop('editing_message_key', None)
    await update.message.reply_text("❌ لغو شد.")
    return ConversationHandler.END


def get_message_customizer_conversation():
    """ConversationHandler"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters
    
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_message, pattern="^msg_start_edit:")],
        states={
            EDIT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )
