"""
مدیریت سفارشات و پرداخت‌ها

"""
import json
import jdatetime
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from logger import log_payment, log_admin_action
from config import ADMIN_ID, MESSAGES, CARD_NUMBER, CARD_HOLDER

# ✅ FIX: اضافه شدن rate limiting
from rate_limiter import rate_limit, action_limit

from keyboards import (
    order_confirmation_keyboard, 
    payment_confirmation_keyboard, 
    user_main_keyboard,
    order_items_removal_keyboard
)
from states import OrderStatus

logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS ====================

def format_jalali_datetime(dt_str):
    """تبدیل تاریخ میلادی به شمسی"""
    try:
        if isinstance(dt_str, str):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = dt_str
        
        jalali = jdatetime.datetime.fromgregorian(datetime=dt)
        return jalali.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str


def get_order_status_emoji(status):
    """ایموجی وضعیت سفارش"""
    status_map = {
        OrderStatus.PENDING: '⏳',
        OrderStatus.WAITING_PAYMENT: '💳',
        OrderStatus.RECEIPT_SENT: '📤',
        OrderStatus.PAYMENT_CONFIRMED: '✅',
        OrderStatus.CONFIRMED: '✅',
        OrderStatus.REJECTED: '❌',
        OrderStatus.EXPIRED: '⏰'
    }
    
    # ✅ مقایسه با Enum
    for key, emoji in status_map.items():
        if status == key:
            return emoji
    
    return '❓'


def get_order_status_text(status):
    """متن وضعیت سفارش"""
    status_map = {
        OrderStatus.PENDING: 'در انتظار تایید',
        OrderStatus.WAITING_PAYMENT: 'در انتظار پرداخت',
        OrderStatus.RECEIPT_SENT: 'رسید ارسال شده',
        OrderStatus.PAYMENT_CONFIRMED: 'تایید شده',
        OrderStatus.CONFIRMED: 'تایید شده',
        OrderStatus.REJECTED: 'رد شده',
        OrderStatus.EXPIRED: 'منقضی شده'
    }
    
    # ✅ مقایسه با Enum
    for key, text in status_map.items():
        if status == key:
            return text
    
    return 'نامشخص'


def is_order_expired(order):
    """
    بررسی منقضی بودن سفارش
    ✅ FIX: این تابع همه جا استفاده میشه
    """
    if not order:
        return True
    
    expires_at = order[11]  # فیلد expires_at
    if not expires_at:
        return False
    
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except:
            return False
    
    return datetime.now() > expires_at


def create_order_action_keyboard(order_id, status, is_expired):
    """
    ساخت دکمه‌های دینامیک بر اساس وضعیت سفارش
    """
    keyboard = []
    
    # سفارشات تکمیل شده → بدون دکمه
    if status == OrderStatus.PAYMENT_CONFIRMED or status == OrderStatus.CONFIRMED:
        return None
    
    # سفارشات منقضی شده → فقط دکمه حذف
    if is_expired:
        keyboard.append([
            InlineKeyboardButton("🗑 حذف سفارش", callback_data=f"delete_order:{order_id}")
        ])
    
    # سفارش در مرحله پرداخت
    elif status == OrderStatus.WAITING_PAYMENT:
        keyboard.append([
            InlineKeyboardButton("💳 ادامه پرداخت", callback_data=f"continue_payment:{order_id}")
        ])
        keyboard.append([
            InlineKeyboardButton("🗑 حذف سفارش", callback_data=f"delete_order:{order_id}")
        ])
    
    # رسید ارسال شده
    elif status == OrderStatus.RECEIPT_SENT:
        keyboard.append([
            InlineKeyboardButton("⏳ منتظر تایید ادمین...", callback_data=f"waiting:{order_id}")
        ])
    
    # در انتظار تایید اولیه
    elif status == OrderStatus.PENDING:
        keyboard.append([
            InlineKeyboardButton("⏳ منتظر بررسی ادمین...", callback_data=f"waiting:{order_id}")
        ])
    
    # رد شده
    elif status == OrderStatus.REJECTED:
        keyboard.append([
            InlineKeyboardButton("🗑 حذف سفارش", callback_data=f"delete_order:{order_id}")
        ])
    
    return InlineKeyboardMarkup(keyboard) if keyboard else None


# ==================== USER HANDLERS ====================

@rate_limit(max_requests=20, window_seconds=60)
async def view_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سفارشات کاربر"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    orders = db.get_user_orders(user_id)
    
    if not orders:
        await update.message.reply_text(
            "📭 شما هنوز سفارشی ثبت نکرده‌اید.",
            reply_markup=user_main_keyboard()
        )
        return
    
    await update.message.reply_text(f"📋 شما {len(orders)} سفارش دارید:")
    
    for order in orders:
        order_id, user_id_val, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        
        # بررسی منقضی بودن
        expired = is_order_expired(order)
        actual_status = OrderStatus.EXPIRED if expired and status not in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.CONFIRMED] else status
        
        # ساخت متن
        text = f"📋 سفارش #{order_id}\n\n"
        text += f"📅 تاریخ: {format_jalali_datetime(created_at)}\n"
        
        # نمایش تاریخ انقضا
        if expires_at and status not in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.CONFIRMED, OrderStatus.REJECTED]:
            text += f"⏰ تاریخ انقضا: {format_jalali_datetime(expires_at)}\n"
            if expired:
                text += "⚠️ این سفارش منقضی شده است!\n"
        
        text += f"📊 وضعیت: {get_order_status_emoji(actual_status)} {get_order_status_text(actual_status)}\n\n"
        
        text += "🛍 محصولات:\n"
        for item in items:
            text += f"▫️ {item['product']} - {item['pack']}\n"
            text += f"   تعداد: {item['quantity']} عدد\n"
        
        text += f"\n💰 مبلغ کل: {total_price:,.0f} تومان\n"
        
        if discount_amount > 0:
            text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
            text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان\n"
        
        if shipping_method:
            shipping_names = {
                'terminal': 'ترمینال 🚌',
                'barbari': 'باربری 🚚',
                'tipax': 'تیپاکس 📦',
                'chapar': 'چاپار 🏃'
            }
            text += f"📦 نحوه ارسال: {shipping_names.get(shipping_method, shipping_method)}\n"
        
        keyboard = create_order_action_keyboard(order_id, actual_status, expired)
        
        await update.message.reply_text(text, reply_markup=keyboard)


@rate_limit(max_requests=10, window_seconds=60)
async def handle_continue_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ادامه فرآیند پرداخت
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.edit_message_text("❌ سفارش یافت نشد!")
        return
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.edit_message_text(
            "⏰ این سفارش منقضی شده است!\n\n"
            "💡 می‌توانید آن را حذف کنید و سفارش جدیدی ثبت کنید."
        )
        logger.info(f"⚠️ تلاش برای ادامه پرداخت سفارش منقضی {order_id}")
        return
    
    final_price = order[5]
    
    message = MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await query.edit_message_text(
        f"💳 **ادامه پرداخت سفارش #{order_id}**\n\n{message}",
        parse_mode='Markdown'
    )


@rate_limit(max_requests=10, window_seconds=60)
async def handle_delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    حذف سفارش توسط کاربر
    ✅ FIX: امکان حذف فقط برای سفارشات منقضی/رد شده
    """
    query = update.callback_query
    
    order_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    status = order[7]
    
    # ✅ فقط سفارشات منقضی یا رد شده قابل حذف هستند
    if status in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.CONFIRMED]:
        await query.answer("⚠️ سفارشات تایید شده قابل حذف نیستند!", show_alert=True)
        return
    
    db.delete_order(order_id)
    
    await query.answer("✅ سفارش حذف شد", show_alert=False)
    await query.edit_message_text(
        "🗑 سفارش با موفقیت حذف شد.\n\n"
        "💡 می‌توانید سفارش جدیدی ثبت کنید."
    )
    
    logger.info(f"🗑 سفارش {order_id} توسط کاربر {user_id} حذف شد")


# ==================== ADMIN HANDLERS ====================

@rate_limit(max_requests=30, window_seconds=60)
async def view_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش سفارشات در انتظار تایید
    ✅ FIX: چک expire اضافه شد
    """
    db = context.bot_data['db']
    
    orders = db.get_pending_orders()
    
    if not orders:
        await update.message.reply_text("هیچ سفارش جدیدی در انتظار تایید نیست.")
        return
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
        
        # ✅ بررسی منقضی بودن
        if is_order_expired(order):
            await update.message.reply_text(
                f"⏰ سفارش #{order_id} منقضی شده است و نیاز به بررسی ندارد.\n"
                f"💡 این سفارش در پاکسازی بعدی حذف خواهد شد."
            )
            logger.info(f"⚠️ سفارش منقضی {order_id} رد اتوماتیک شد")
            continue
        
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        text = f"📋 سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        # نمایش تاریخ انقضا
        if expires_at:
            jalali_expires = format_jalali_datetime(expires_at)
            text += f"⏰ تاریخ انقضا: {jalali_expires}\n\n"
        
        for item in items:
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد - {item['price']:,.0f} تومان\n"
        
        text += f"\n💰 مبلغ کل: {total_price:,.0f} تومان"
        
        if discount_amount > 0:
            text += f"\n🎁 تخفیف ({discount_code}): {discount_amount:,.0f} تومان"
            text += f"\n💳 مبلغ نهایی: {final_price:,.0f} تومان"
        
        await update.message.reply_text(
            text,
            reply_markup=order_confirmation_keyboard(order_id)
        )


@rate_limit(max_requests=20, window_seconds=60)
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تایید سفارش توسط ادمین
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer("✅ سفارش تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        logger.warning(f"⚠️ تلاش برای تایید سفارش منقضی {order_id}")
        return
    
    db.update_order_status(order_id, OrderStatus.WAITING_PAYMENT)
    
    user_id = order[1]
    final_price = order[5]
    
    message = MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message, parse_mode='Markdown')
    
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد - در انتظار پرداخت"
    )
    
    log_admin_action(ADMIN_ID, f"تایید سفارش {order_id}")
    logger.info(f"✅ سفارش {order_id} توسط ادمین تایید شد")


@rate_limit(max_requests=20, window_seconds=60)
async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    رد سفارش توسط ادمین
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer("❌ سفارش رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        logger.warning(f"⚠️ تلاش برای رد سفارش منقضی {order_id}")
        return
    
    db.update_order_status(order_id, OrderStatus.REJECTED)
    
    user_id = order[1]
    
    await context.bot.send_message(user_id, MESSAGES["order_rejected"])
    
    await query.edit_message_text(
        query.message.text + "\n\n❌ رد شد"
    )
    
    log_admin_action(ADMIN_ID, f"رد سفارش {order_id}")
    logger.info(f"❌ سفارش {order_id} توسط ادمین رد شد")


@rate_limit(max_requests=20, window_seconds=60)
async def remove_item_from_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    حذف آیتم از سفارش
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        logger.warning(f"⚠️ تلاش برای ویرایش سفارش منقضی {order_id}")
        return
    
    items = json.loads(order[2])
    
    if item_index < 0 or item_index >= len(items):
        await query.answer("❌ خطا در حذف آیتم")
        return
    
    removed_item = items.pop(item_index)
    
    if len(items) == 0:
        await query.answer("❌ نمی‌توان تمام آیتم‌ها را حذف کرد. برای رد کامل از دکمه 'رد سفارش' استفاده کنید.", show_alert=True)
        return
    
    new_total = sum(item['price'] * item['quantity'] for item in items)
    discount_amount = order[4]
    new_final = max(0, new_total - discount_amount)
    
    db.update_order_items(order_id, items, new_total, new_final)
    
    await query.answer(f"✅ {removed_item['product']} حذف شد")
    
    updated_order = db.get_order(order_id)
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = updated_order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"📋 سفارش #{order_id} (ویرایش شده)\n\n"
    text += f"👤 {first_name} (@{username})\n"
    text += f"📝 نام: {full_name}\n"
    text += f"📞 {phone}\n"
    text += f"📍 {address}\n\n"
    
    for item in items:
        text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            text += f"\n  📝 {item['admin_notes']}"
        
        text += "\n"
    
    text += f"\n💰 {final_price:,.0f} تومان"
    
    await query.edit_message_text(
        text,
        reply_markup=order_items_removal_keyboard(order_id, items)
    )
    
    logger.info(f"🗑 آیتم {item_index} از سفارش {order_id} حذف شد")


@rate_limit(max_requests=20, window_seconds=60)
async def reject_full_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    رد کامل سفارش بدون تایید
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer("❌ سفارش کامل رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        logger.warning(f"⚠️ تلاش برای رد سفارش منقضی {order_id}")
        return
    
    db.update_order_status(order_id, OrderStatus.REJECTED)
    
    user_id = order[1]
    await context.bot.send_message(user_id, MESSAGES["order_rejected"])
    
    await query.edit_message_text(
        query.message.text + "\n\n❌ سفارش کامل رد شد"
    )
    
    log_admin_action(ADMIN_ID, f"رد کامل سفارش {order_id}")
    logger.info(f"❌ سفارش {order_id} به صورت کامل رد شد")


@rate_limit(max_requests=20, window_seconds=60)
async def back_to_order_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بازگشت به بررسی سفارش
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        logger.warning(f"⚠️ تلاش برای بازگشت به سفارش منقضی {order_id}")
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"📋 سفارش #{order_id}\n\n"
    text += f"👤 {first_name} (@{username})\n"
    text += f"📝 نام: {full_name}\n"
    text += f"📞 {phone}\n"
    text += f"📍 {address}\n\n"
    
    for item in items:
        text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            text += f"\n  📝 {item['admin_notes']}"
        
        text += "\n"
    
    text += f"\n💰 {final_price:,.0f} تومان"
    
    await query.edit_message_text(
        text,
        reply_markup=order_confirmation_keyboard(order_id)
    )


@rate_limit(max_requests=20, window_seconds=60)
async def confirm_modified_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تایید سفارش با تغییرات
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer("✅ سفارش با تغییرات تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        logger.warning(f"⚠️ تلاش برای تایید سفارش منقضی {order_id}")
        return
    
    db.update_order_status(order_id, OrderStatus.WAITING_PAYMENT)
    
    user_id = order[1]
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    
    message = "✅ **سفارش شما با تغییرات تایید شد!**\n"
    message += "⚠️ مدل‌های ناموجود از فاکتور شما حذف شدند.\n\n"
    message += "📦 آیتم‌های تایید شده:\n\n"
    
    for item in items:
        message += f"• {item['product']} - {item['pack']}\n"
        message += f"  {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            message += f"\n  📝 {item['admin_notes']}"
        
        message += f" - {item['price']:,.0f} تومان\n\n"
    
    message += f"💳 مبلغ قابل پرداخت: {final_price:,.0f} تومان\n\n"
    message += MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message, parse_mode='Markdown')
    
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد با تغییرات - در انتظار پرداخت"
    )
    
    logger.info(f"✅ سفارش {order_id} با تغییرات توسط ادمین تایید شد")


# ==================== PAYMENT HANDLERS ====================

@rate_limit(max_requests=10, window_seconds=60)
async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت رسید از کاربر"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    orders = db.get_waiting_payment_orders()
    user_order = None
    
    for order in orders:
        if order[1] == user_id:
            user_order = order
            break
    
    if not user_order:
        await update.message.reply_text("شما سفارش در انتظار پرداختی ندارید.")
        return
    
    order_id = user_order[0]
    photo = update.message.photo[-1]
    
    db.add_receipt(order_id, photo.file_id)
    db.update_order_status(order_id, OrderStatus.RECEIPT_SENT)
    
    await update.message.reply_text(MESSAGES["receipt_received"])
    
    order = db.get_order(order_id)
    items = json.loads(order[2])
    final_price = order[5]
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    
    text = f"💳 رسید سفارش #{order_id}\n\n"
    text += f"👤 {first_name} (@{username})\n"
    text += f"💰 مبلغ: {final_price:,.0f} تومان\n\n"
    
    for item in items:
        text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            text += f"\n  📝 {item['admin_notes']}"
        
        text += "\n"
    
    await context.bot.send_photo(
        ADMIN_ID,
        photo.file_id,
        caption=text,
        reply_markup=payment_confirmation_keyboard(order_id)
    )
    
    logger.info(f"📷 رسید سفارش {order_id} دریافت شد")


@rate_limit(max_requests=30, window_seconds=60)
async def view_payment_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش رسیدهای در انتظار تایید"""
    db = context.bot_data['db']
    
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
        (OrderStatus.RECEIPT_SENT,)
    )
    query_result = cursor.fetchall()
    
    if not query_result:
        await update.message.reply_text("هیچ رسیدی در انتظار تایید نیست.")
        return
    
    for order in query_result:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt_photo, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        
        text = f"💳 رسید سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"💰 {final_price:,.0f} تومان\n\n"
        
        for item in items:
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
            
            if item.get('admin_notes'):
                text += f"\n  📝 {item['admin_notes']}"
            
            text += "\n"
        
        if receipt_photo:
            await update.message.reply_photo(
                receipt_photo,
                caption=text,
                reply_markup=payment_confirmation_keyboard(order_id)
            )


@rate_limit(max_requests=20, window_seconds=60)
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید پرداخت توسط ادمین"""
    query = update.callback_query
    await query.answer("✅ پرداخت تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, OrderStatus.PAYMENT_CONFIRMED)
    
    order = db.get_order(order_id)
    user_id = order[1]
    log_payment(order_id, user_id, "confirmed")
    
    from keyboards import shipping_method_keyboard
    
    await context.bot.send_message(
        user_id,
        "✅ رسید شما تایید شد!\n\n"
        "📦 لطفاً نحوه ارسال خود را انتخاب کنید:",
        reply_markup=shipping_method_keyboard()
    )
    
    context.bot_data[f'pending_shipping_{user_id}'] = order_id
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ تایید شد - منتظر انتخاب نحوه ارسال"
    )
    
    logger.info(f"✅ پرداخت سفارش {order_id} تایید شد")


@rate_limit(max_requests=20, window_seconds=60)
async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد پرداخت توسط ادمین"""
    query = update.callback_query
    await query.answer("❌ رسید رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, OrderStatus.WAITING_PAYMENT)
    
    order = db.get_order(order_id)
    user_id = order[1]
    final_price = order[5]
    
    message = MESSAGES["payment_rejected"] + "\n\n"
    message += MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message)
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ رد شد - منتظر رسید جدید"
    )
    
    logger.info(f"❌ رسید سفارش {order_id} رد شد")


# ==================== QUANTITY MANAGEMENT ====================

@rate_limit(max_requests=20, window_seconds=60)
async def increase_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزایش تعداد یک آیتم"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        return
    
    items = json.loads(order[2])
    
    if 0 <= item_index < len(items):
        items[item_index]['quantity'] += 1
        
        new_total = sum(item['price'] * item['quantity'] for item in items)
        discount_amount = order[4]
        new_final = max(0, new_total - discount_amount)
        
        db.update_order_items(order_id, items, new_total, new_final)
        
        await query.answer(f"✅ تعداد {items[item_index]['product']} افزایش یافت")
        
        # به‌روزرسانی پیام
        updated_order = db.get_order(order_id)
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = updated_order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        text = f"📋 سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        for item in items:
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
            
            if item.get('admin_notes'):
                text += f"\n  📝 {item['admin_notes']}"
            
            text += "\n"
        
        text += f"\n💰 {final_price:,.0f} تومان"
        
        await query.edit_message_text(
            text,
            reply_markup=order_items_removal_keyboard(order_id, items)
        )


@rate_limit(max_requests=20, window_seconds=60)
async def decrease_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاهش تعداد یک آیتم"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if is_order_expired(order):
        await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
        return
    
    items = json.loads(order[2])
    
    if 0 <= item_index < len(items):
        if items[item_index]['quantity'] > 1:
            items[item_index]['quantity'] -= 1
            
            new_total = sum(item['price'] * item['quantity'] for item in items)
            discount_amount = order[4]
            new_final = max(0, new_total - discount_amount)
            
            db.update_order_items(order_id, items, new_total, new_final)
            
            await query.answer(f"✅ تعداد {items[item_index]['product']} کاهش یافت")
        else:
            await query.answer("⚠️ حداقل تعداد 1 عدد است. برای حذف از دکمه 'حذف' استفاده کنید.", show_alert=True)
            return
        
        # به‌روزرسانی پیام
        updated_order = db.get_order(order_id)
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = updated_order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        text = f"📋 سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        for item in items:
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
            
            if item.get('admin_notes'):
                text += f"\n  📝 {item['admin_notes']}"
            
            text += "\n"
        
        text += f"\n💰 {final_price:,.0f} تومان"
        
        await query.edit_message_text(
            text,
            reply_markup=order_items_removal_keyboard(order_id, items)
        )
