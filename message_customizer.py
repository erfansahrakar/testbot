"""
✅ FEATURE #5: سفارشی‌سازی پیام‌های ربات
ادمین می‌تونه متن پیام‌های بات رو تغییر بده
"""
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID

logger = logging.getLogger(__name__)

# States
EDIT_MESSAGE = 1

# فایل ذخیره پیام‌های سفارشی
CUSTOM_MESSAGES_FILE = "/home/claude/custom_messages.json"

# پیام‌های پیش‌فرض
DEFAULT_MESSAGES = {
    "start_user": "👋 سلام {name}!\n\n🛍 به فروشگاه ما خوش آمدید.\n\nلطفاً از منوی زیر استفاده کنید:",
    "start_admin": "👋 سلام ادمین عزیز!\n\n🎛 به پنل مدیریت خوش آمدید.",
    "product_added": "✅ محصول با موفقیت ثبت شد!",
    "order_confirmed": "✅ سفارش شما تایید شد!\n\n📦 به‌زودی ارسال خواهد شد.",
    "order_rejected": "❌ متأسفانه سفارش شما رد شد.\n\nلطفاً با پشتیبانی تماس بگیرید.",
    "payment_waiting": "💳 لطفاً رسید پرداخت خود را ارسال کنید.\n\n⏰ زمان: {minutes} دقیقه",
    "discount_applied": "🎁 تخفیف با موفقیت اعمال شد!\n\n💰 مبلغ تخفیف: {amount:,} تومان",
    "cart_empty": "🛒 سبد خرید شما خالی است!\n\nاز منوی اصلی محصولات را مشاهده کنید.",
    "welcome_back": "👋 خوش آمدید!\n\nچه کمکی می‌تونیم بکنیم؟",
    "order_shipped": "📦 سفارش شما ارسال شد!\n\n🚚 کد رهگیری: {tracking_code}",
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
            **kwargs: متغیرهایی که باید جایگزین بشن (مثل {name})
        
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


# Instance global
message_customizer = MessageCustomizer()


# ==================== Handler Functions ====================

async def customize_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی سفارشی‌سازی پیام‌ها"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = []
    
    # لیست پیام‌ها
    for key in message_customizer.get_all_keys():
        # چک کن سفارشی شده یا نه
        is_custom = key in message_customizer.custom_messages
        emoji = "✏️" if is_custom else "📝"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {key}",
                callback_data=f"msg_edit:{key}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_admin")
    ])
    
    text = (
        "⚙️ **سفارشی‌سازی پیام‌ها**\n\n"
        "📝 = پیش‌فرض\n"
        "✏️ = سفارشی شده\n\n"
        "برای ویرایش یک پیام، روی آن کلیک کنید:"
    )
    
    # ✅ چک کنیم از message فراخوانی شده یا callback
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        logger.warning("customize_messages_menu called without message or callback_query")



async def show_message_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پیش‌نمایش پیام"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    key = query.data.split(':')[1]
    
    # دریافت پیام فعلی
    current_message = message_customizer.get_message(key)
    is_custom = key in message_customizer.custom_messages
    default_message = DEFAULT_MESSAGES.get(key, "")
    
    # نمایش
    text = f"📝 **ویرایش پیام: `{key}`**\n\n"
    text += f"{'✏️ متن فعلی (سفارشی):' if is_custom else '📝 متن فعلی (پیش‌فرض):'}\n"
    text += f"```\n{current_message}\n```\n\n"
    
    if is_custom and default_message:
        text += f"📌 متن پیش‌فرض:\n"
        text += f"```\n{default_message}\n```\n\n"
    
    text += "💡 متغیرهای قابل استفاده:\n"
    text += "• `{name}` - نام کاربر\n"
    text += "• `{amount}` - مبلغ\n"
    text += "• `{minutes}` - دقیقه\n"
    text += "• `{tracking_code}` - کد رهگیری\n"
    
    keyboard = [
        [InlineKeyboardButton("✏️ ویرایش", callback_data=f"msg_start_edit:{key}")],
    ]
    
    if is_custom:
        keyboard.append([
            InlineKeyboardButton("🔄 بازگشت به پیش‌فرض", callback_data=f"msg_reset:{key}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="msg_back_to_list")
    ])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def start_edit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش پیام"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    key = query.data.split(':')[1]
    context.user_data['editing_message_key'] = key
    
    await query.edit_message_text(
        f"✏️ **ویرایش پیام: `{key}`**\n\n"
        "لطفاً متن جدید را ارسال کنید:\n\n"
        "💡 می‌توانید از متغیرها استفاده کنید:\n"
        "• `{name}` - نام کاربر\n"
        "• `{amount}` - مبلغ\n"
        "• `{minutes}` - دقیقه\n"
        "• `{tracking_code}` - کد رهگیری\n\n"
        "برای لغو، /cancel را ارسال کنید.",
        parse_mode='Markdown'
    )
    
    return EDIT_MESSAGE


async def receive_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن جدید پیام"""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    # ✅ چک کردن وجود update.message
    if not update.message:
        logger.warning("receive_new_message called without message")
        return ConversationHandler.END
    
    key = context.user_data.get('editing_message_key')
    if not key:
        await update.message.reply_text("❌ خطا! لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    
    new_message = update.message.text
    
    # ذخیره
    if message_customizer.set_message(key, new_message):
        # پاک کردن key قبل از ارسال پیام
        context.user_data.pop('editing_message_key', None)
        
        await update.message.reply_text(
            f"✅ پیام `{key}` با موفقیت به‌روز شد!\n\n"
            f"📝 متن جدید:\n```\n{new_message}\n```\n\n"
            "برای بازگشت به منو از دکمه زیر استفاده کنید:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="msg_back_to_list")
            ]])
        )
    else:
        context.user_data.pop('editing_message_key', None)
        await update.message.reply_text(
            "❌ خطا در ذخیره پیام!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="msg_back_to_list")
            ]])
        )
    
    return ConversationHandler.END


async def reset_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به پیام پیش‌فرض"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    key = query.data.split(':')[1]
    
    if message_customizer.reset_message(key):
        default_message = DEFAULT_MESSAGES.get(key, "")
        await query.edit_message_text(
            f"✅ پیام `{key}` به حالت پیش‌فرض بازگشت!\n\n"
            f"📝 متن پیش‌فرض:\n```\n{default_message}\n```",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ خطا در بازگشت به پیش‌فرض!")


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ویرایش"""
    context.user_data.pop('editing_message_key', None)
    await update.message.reply_text("❌ ویرایش لغو شد.")
    return ConversationHandler.END


# Conversation Handler برای ویرایش پیام
def get_message_customizer_conversation():
    """دریافت ConversationHandler برای سفارشی‌سازی پیام‌ها"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters
    
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_edit_message, pattern="^msg_start_edit:")
        ],
        states={
            EDIT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_message),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_edit),
        ],
        allow_reentry=False,  # ✅ جلوگیری از ورود مجدد به conversation
        per_message=False,
        per_chat=True,
        per_user=True,
    )
