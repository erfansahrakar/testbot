"""
سیستم مدیریت اعتبار (Wallet) برای کاربران
✨ قابلیت‌ها:
- شارژ اعتبار توسط ادمین
- مشاهده موجودی اعتبار
- استفاده از اعتبار در فاکتور نهایی
- اضافه کردن اعتبار هدیه (درصدی یا مبلغ ثابت)
- سیستم کش‌بک خودکار
- تاریخ انقضای اعتبار
- تاریخچه تراکنش‌ها
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# ==================== States ====================
WALLET_CHARGE_USER_ID = 100
WALLET_CHARGE_AMOUNT = 101
WALLET_GIFT_USER_ID = 102
WALLET_GIFT_TYPE = 103
WALLET_GIFT_VALUE = 104
WALLET_GIFT_EXPIRY = 105
WALLET_CASHBACK_PERCENT = 106
WALLET_CASHBACK_DATES = 107

# ==================== توابع Helper ====================

def format_price(price: float) -> str:
    """فرمت کردن قیمت به صورت فارسی"""
    return f"{price:,.0f}".replace(',', '٬')

def get_wallet_keyboard():
    """کیبورد منوی اعتبار"""
    keyboard = [
        [InlineKeyboardButton("💰 مشاهده موجودی", callback_data="wallet:view")],
        [InlineKeyboardButton("📋 تاریخچه تراکنش‌ها", callback_data="wallet:history")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_wallet_keyboard():
    """کیبورد مدیریت اعتبار برای ادمین"""
    keyboard = [
        [InlineKeyboardButton("💳 شارژ اعتبار مشتری", callback_data="wallet_admin:charge")],
        [InlineKeyboardButton("🎁 اعتبار هدیه", callback_data="wallet_admin:gift")],
        [InlineKeyboardButton("💎 تنظیم کش‌بک", callback_data="wallet_admin:cashback")],
        [InlineKeyboardButton("📊 گزارش اعتبارها", callback_data="wallet_admin:report")],
        [InlineKeyboardButton("🔙 بازگشت به منوی ادمین", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== توابع کاربر ====================

async def view_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش موجودی اعتبار کاربر"""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        message_func = query.message.reply_text
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text
    
    db = context.bot_data['db']
    wallet_info = db.get_wallet_balance(user_id)
    
    if not wallet_info:
        text = "💰 **موجودی اعتبار شما**\n\n"
        text += "موجودی فعلی: ۰ تومان\n\n"
        text += "⚠️ شما هنوز اعتباری ندارید.\n"
        text += "با خرید از فروشگاه، اعتبار کسب کنید!"
    else:
        balance, expires_at = wallet_info
        text = "💰 **موجودی اعتبار شما**\n\n"
        text += f"💵 موجودی فعلی: {format_price(balance)} تومان\n\n"
        
        if expires_at:
            expiry_date = datetime.fromisoformat(expires_at)
            if expiry_date > datetime.now():
                text += f"📅 تاریخ انقضا: {expiry_date.strftime('%Y/%m/%d')}\n"
            else:
                text += "⚠️ اعتبار شما منقضی شده است!\n"
        else:
            text += "♾ بدون تاریخ انقضا\n"
        
        text += "\n💡 از اعتبار خود در خریدهای بعدی استفاده کنید!"
    
    await message_func(text, parse_mode='Markdown', reply_markup=get_wallet_keyboard())

async def view_wallet_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش تاریخچه تراکنش‌های اعتبار"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db = context.bot_data['db']
    
    transactions = db.get_wallet_transactions(user_id, limit=10)
    
    if not transactions:
        text = "📋 **تاریخچه تراکنش‌ها**\n\n"
        text += "هنوز تراکنشی ثبت نشده است."
    else:
        text = "📋 **تاریخچه تراکنش‌ها**\n\n"
        text += "🔽 ۱۰ تراکنش اخیر:\n\n"
        
        for trans in transactions:
            trans_id, amount, trans_type, description, created_at = trans
            date = datetime.fromisoformat(created_at).strftime('%Y/%m/%d %H:%M')
            
            if amount > 0:
                emoji = "➕"
                sign = "+"
            else:
                emoji = "➖"
                sign = ""
            
            text += f"{emoji} {sign}{format_price(abs(amount))} تومان\n"
            text += f"   📝 {description}\n"
            text += f"   🕐 {date}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="wallet:view")]]
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def use_wallet_in_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استفاده از اعتبار در پرداخت سفارش"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    order_id = int(query.data.split(":")[1])
    
    db = context.bot_data['db']
    
    # دریافت اطلاعات سفارش
    order = db.get_order(order_id)
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    _, _, _, _, _, final_price, _, status, _, _, _ = order
    
    if status not in ['pending', 'waiting_payment']:
        await query.answer("⚠️ این سفارش قابل پرداخت نیست!", show_alert=True)
        return
    
    # دریافت موجودی اعتبار
    wallet_info = db.get_wallet_balance(user_id)
    
    if not wallet_info or wallet_info[0] <= 0:
        await query.answer("❌ موجودی اعتبار شما کافی نیست!", show_alert=True)
        return
    
    wallet_balance = wallet_info[0]
    
    # محاسبه مبلغ قابل استفاده
    usable_amount = min(wallet_balance, final_price)
    new_final_price = final_price - usable_amount
    
    # کسر از اعتبار
    success = db.deduct_wallet(
        user_id=user_id,
        amount=usable_amount,
        description=f"پرداخت سفارش #{order_id}",
        order_id=order_id
    )
    
    if not success:
        await query.answer("❌ خطا در استفاده از اعتبار!", show_alert=True)
        return
    
    # به‌روزرسانی مبلغ سفارش
    db.update_order_wallet_payment(order_id, usable_amount, new_final_price)
    
    if new_final_price <= 0:
        # سفارش کاملاً با اعتبار پرداخت شد
        db.update_order_status(order_id, 'payment_confirmed')
        text = f"✅ **پرداخت موفق!**\n\n"
        text += f"💰 {format_price(usable_amount)} تومان از اعتبار شما کسر شد.\n"
        text += f"✨ سفارش شما تایید شد و به زودی ارسال می‌شود!"
    else:
        text = f"✅ **اعتبار اعمال شد!**\n\n"
        text += f"💰 {format_price(usable_amount)} تومان از اعتبار شما استفاده شد.\n"
        text += f"💵 مبلغ باقیمانده: {format_price(new_final_price)} تومان\n\n"
        text += "لطفاً مبلغ باقیمانده را واریز کنید."
    
    await query.message.reply_text(text, parse_mode='Markdown')

# ==================== توابع ادمین ====================

async def admin_wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی مدیریت اعتبار برای ادمین"""
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message_func = query.message.reply_text
    else:
        message_func = update.message.reply_text
    
    text = "🏦 **مدیریت سیستم اعتبار**\n\n"
    text += "از این بخش می‌توانید:\n"
    text += "• شارژ اعتبار مشتریان\n"
    text += "• اعتبار هدیه بدهید\n"
    text += "• کش‌بک تنظیم کنید\n"
    text += "• گزارش اعتبارها را ببینید"
    
    await message_func(text, parse_mode='Markdown', reply_markup=get_admin_wallet_keyboard())

async def admin_charge_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع شارژ اعتبار توسط ادمین"""
    query = update.callback_query
    await query.answer()
    
    from keyboards import cancel_keyboard
    
    await query.message.reply_text(
        "💳 **شارژ اعتبار مشتری**\n\n"
        "لطفاً User ID مشتری را وارد کنید:",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return WALLET_CHARGE_USER_ID

async def admin_charge_wallet_user_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت User ID برای شارژ"""
    if update.message.text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        return ConversationHandler.END
    
    try:
        user_id = int(update.message.text)
        context.user_data['wallet_charge_user_id'] = user_id
        
        from keyboards import cancel_keyboard
        
        await update.message.reply_text(
            f"✅ کاربر: {user_id}\n\n"
            "💰 مبلغ شارژ را وارد کنید (به تومان):",
            reply_markup=cancel_keyboard()
        )
        
        return WALLET_CHARGE_AMOUNT
    
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return WALLET_CHARGE_USER_ID

async def admin_charge_wallet_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مبلغ و شارژ اعتبار"""
    if update.message.text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        amount = float(update.message.text.replace(',', ''))
        user_id = context.user_data.get('wallet_charge_user_id')
        
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد!")
            return WALLET_CHARGE_AMOUNT
        
        db = context.bot_data['db']
        success = db.add_wallet_balance(
            user_id=user_id,
            amount=amount,
            description="شارژ توسط ادمین",
            admin_id=update.effective_user.id
        )
        
        if success:
            from keyboards import admin_main_keyboard
            
            await update.message.reply_text(
                f"✅ شارژ موفق!\n\n"
                f"👤 کاربر: {user_id}\n"
                f"💰 مبلغ: {format_price(amount)} تومان\n\n"
                f"اعتبار کاربر شارژ شد.",
                reply_markup=admin_main_keyboard()
            )
            
            # اطلاع‌رسانی به کاربر
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **اعتبار شما شارژ شد!**\n\n"
                         f"💰 مبلغ: {format_price(amount)} تومان\n"
                         f"✨ از خرید بعدی خود می‌توانید استفاده کنید!",
                    parse_mode='Markdown'
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ خطا در شارژ اعتبار!")
        
        context.user_data.clear()
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return WALLET_CHARGE_AMOUNT

async def admin_gift_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع اعتبار هدیه"""
    query = update.callback_query
    await query.answer()

    from keyboards import cancel_keyboard

    await query.message.reply_text(
        "🎁 **اعتبار هدیه**\n\n"
        "لطفاً User ID مشتری را وارد کنید:\n"
        "(یا عدد 0 برای همه کاربران)",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    return WALLET_GIFT_USER_ID


async def admin_gift_user_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت User ID برای هدیه"""
    if update.message.text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        return ConversationHandler.END

    try:
        user_id = int(update.message.text)
        context.user_data['gift_user_id'] = user_id

        from keyboards import cancel_keyboard

        keyboard = [
            ["💰 مبلغ ثابت"],
            ["📊 درصدی"],
            ["❌ لغو"]
        ]
        from telegram import ReplyKeyboardMarkup
        await update.message.reply_text(
            "نوع اعتبار هدیه را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return WALLET_GIFT_TYPE

    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return WALLET_GIFT_USER_ID


async def admin_gift_type_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نوع هدیه"""
    text = update.message.text

    if text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        context.user_data.clear()
        return ConversationHandler.END

    if text == "💰 مبلغ ثابت":
        context.user_data['gift_type'] = 'fixed'
        label = "مبلغ (تومان)"
    elif text == "📊 درصدی":
        context.user_data['gift_type'] = 'percent'
        label = "درصد (1 تا 100)"
    else:
        await update.message.reply_text("❌ گزینه نامعتبر!")
        return WALLET_GIFT_TYPE

    from keyboards import cancel_keyboard
    await update.message.reply_text(
        f"💡 {label} را وارد کنید:",
        reply_markup=cancel_keyboard()
    )
    return WALLET_GIFT_VALUE


async def admin_gift_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مقدار هدیه و اعمال"""
    if update.message.text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        context.user_data.clear()
        return ConversationHandler.END

    try:
        value = float(update.message.text.replace(',', ''))
        gift_type = context.user_data.get('gift_type')
        target_user_id = context.user_data.get('gift_user_id')

        if gift_type == 'percent' and not (1 <= value <= 100):
            await update.message.reply_text("❌ درصد باید بین 1 تا 100 باشد!")
            return WALLET_GIFT_VALUE

        db = context.bot_data['db']

        if target_user_id == 0:
            # هدیه به همه کاربران
            users = db.get_all_users()
            count = 0
            for user in users:
                uid = user[0]
                if gift_type == 'fixed':
                    amount = value
                else:
                    wallet = db.get_wallet_balance(uid)
                    bal = wallet[0] if wallet else 0
                    amount = bal * value / 100

                if amount > 0:
                    db.add_wallet_balance(
                        user_id=uid,
                        amount=amount,
                        description=f"اعتبار هدیه از ادمین",
                        admin_id=update.effective_user.id
                    )
                    count += 1

            await update.message.reply_text(
                f"✅ اعتبار هدیه به {count} کاربر اعمال شد.",
                reply_markup=__import__('keyboards').admin_main_keyboard()
            )
        else:
            if gift_type == 'fixed':
                amount = value
            else:
                wallet = db.get_wallet_balance(target_user_id)
                bal = wallet[0] if wallet else 0
                amount = bal * value / 100

            success = db.add_wallet_balance(
                user_id=target_user_id,
                amount=amount,
                description="اعتبار هدیه از ادمین",
                admin_id=update.effective_user.id
            )

            if success:
                await update.message.reply_text(
                    f"✅ **اعتبار هدیه اعمال شد!**\n\n"
                    f"👤 کاربر: {target_user_id}\n"
                    f"💰 مبلغ: {format_price(amount)} تومان",
                    parse_mode='Markdown',
                    reply_markup=__import__('keyboards').admin_main_keyboard()
                )
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"🎁 **اعتبار هدیه دریافت کردید!**\n\n"
                             f"💰 مبلغ: {format_price(amount)} تومان\n"
                             f"✨ از این اعتبار در خریدهای بعدی استفاده کنید!",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            else:
                await update.message.reply_text("❌ خطا در اعمال هدیه!")

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return WALLET_GIFT_VALUE


async def admin_cashback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم کش‌بک"""
    query = update.callback_query
    await query.answer()

    from keyboards import cancel_keyboard

    await query.message.reply_text(
        "💎 **تنظیم کش‌بک**\n\n"
        "درصد کش‌بک را وارد کنید (1 تا 50):\n\n"
        "💡 کش‌بک بعد از تایید هر سفارش به‌صورت اعتبار به کاربر داده می‌شود.\n"
        "عدد 0 = غیرفعال کردن کش‌بک",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    return WALLET_CASHBACK_PERCENT


async def admin_cashback_percent_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت درصد کش‌بک و ذخیره"""
    if update.message.text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        return ConversationHandler.END

    try:
        percent = float(update.message.text.replace(',', ''))

        if percent < 0 or percent > 50:
            await update.message.reply_text("❌ درصد باید بین 0 تا 50 باشد!")
            return WALLET_CASHBACK_PERCENT

        # ذخیره در bot_data و دیتابیس (برای ماندگاری پس از ریستارت)
        context.bot_data['cashback_percent'] = percent
        db = context.bot_data['db']
        db.set_setting('cashback_percent', percent)

        from keyboards import admin_main_keyboard

        if percent == 0:
            msg = "✅ کش‌بک **غیرفعال** شد."
        else:
            msg = (
                f"✅ **کش‌بک تنظیم شد!**\n\n"
                f"💎 درصد کش‌بک: {percent}%\n\n"
                f"از این به بعد بعد از تایید هر سفارش، {percent}% مبلغ به اعتبار کاربر اضافه می‌شود."
            )

        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=admin_main_keyboard())
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return WALLET_CASHBACK_PERCENT


async def admin_wallet_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """گزارش کلی اعتبارهای کاربران"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    report = db.get_wallet_statistics()
    
    text = "📊 **گزارش سیستم اعتبار**\n\n"
    text += f"👥 تعداد کاربران با اعتبار: {report['total_users']}\n"
    text += f"💰 مجموع اعتبارها: {format_price(report['total_balance'])} تومان\n"
    text += f"💵 میانگین اعتبار: {format_price(report['avg_balance'])} تومان\n"
    text += f"💎 بیشترین اعتبار: {format_price(report['max_balance'])} تومان\n\n"
    text += f"📈 تراکنش‌های امروز: {report['today_transactions']}\n"
    text += f"💸 مجموع شارژ امروز: {format_price(report['today_charges'])} تومان\n"
    text += f"💳 مجموع برداشت امروز: {format_price(report['today_withdrawals'])} تومان"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="wallet_admin:menu")]]
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
