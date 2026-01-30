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
from config import ADMIN_ID, MESSAGES, CARD_NUMBER, CARD_HOLDER, IBAN_NUMBER
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
        iban=IBAN_NUMBER,
        holder=CARD_HOLDER
    )
    
    await query.edit_message_text(
        f"💳 **ادامه پرداخت سفارش #{order_id}**\n\n{message}",
        parse_mode='Markdown'
    )


async def handle_delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف سفارش توسط کاربر"""
    query = update.callback_query
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    # بررسی مالکیت
    order = db.get_order(order_id)
    if not order or order[1] != update.effective_user.id:
        await query.answer("❌ شما مجاز به حذف این سفارش نیستید!", show_alert=True)
        return
    
    # بررسی وضعیت
    status = order[7]
    if status == OrderStatus.PAYMENT_CONFIRMED or status == OrderStatus.CONFIRMED:
        await query.answer(
            "⚠️ سفارشات تکمیل شده قابل حذف نیستند!\n\n"
            "💡 این سفارش در سوابق شما باقی می‌ماند.",
            show_alert=True
        )
        return
    
    # حذف سفارش
    success = db.delete_order(order_id)
    
    if success:
        await query.answer("✅ سفارش حذف شد", show_alert=True)
        await query.edit_message_text(
            f"🗑 سفارش #{order_id} با موفقیت حذف شد.\n\n"
            "برای مشاهده سفارشات دیگر از منوی اصلی استفاده کنید."
        )
        logger.info(f"✅ سفارش {order_id} توسط کاربر {update.effective_user.id} حذف شد")
    else:
        await query.answer("❌ خطا در حذف سفارش!", show_alert=True)
        logger.error(f"❌ خطا در حذف سفارش {order_id}")


# ==================== ADMIN HANDLERS ====================

async def send_order_to_admin(context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """ارسال سفارش به ادمین"""
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        logger.error(f"❌ سفارش {order_id} یافت نشد برای ارسال به ادمین")
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"🆕 سفارش جدید #{order_id_val}\n\n"
    text += f"👤 کاربر: {first_name} (@{username})\n"
    text += f"📝 نام: {full_name}\n"
    text += f"📞 تلفن: {phone}\n"
    text += f"📍 آدرس: {address}\n\n"
    text += "📦 آیتم‌ها:\n"
    
    for item in items:
        text += f"• {item['product']} - {item['pack']}\n"
        text += f"  تعداد: {item['quantity']} عدد\n"
        
        if item.get('admin_notes'):
            text += f"  📝 توضیحات: {item['admin_notes']}\n"
        
        text += f"  قیمت: {item['price']:,.0f} تومان\n\n"
    
    text += f"💰 جمع کل: {total_price:,.0f} تومان\n"
    
    if discount_amount > 0:
        text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
        if discount_code:
            text += f"🎫 کد تخفیف: {discount_code}\n"
        text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان\n"
    
    text += f"\n📅 تاریخ: {format_jalali_datetime(created_at)}\n"
    text += f"⏰ انقضا: {format_jalali_datetime(expires_at)}"
    
    try:
        await context.bot.send_message(
            ADMIN_ID,
            text,
            reply_markup=order_confirmation_keyboard(order_id_val)
        )
        logger.info(f"✅ سفارش {order_id_val} به ادمین ارسال شد")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال سفارش {order_id_val} به ادمین: {e}")


async def view_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سفارشات در انتظار"""
    db = context.bot_data['db']
    orders = db.get_pending_orders()
    
    if not orders:
        await update.message.reply_text("هیچ سفارش جدیدی وجود ندارد.")
        return
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        # بررسی منقضی بودن
        expired = is_order_expired(order)
        
        text = f"📋 سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        if expired:
            text += "⚠️ **این سفارش منقضی شده است!**\n\n"
        
        for item in items:
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
            
            if item.get('admin_notes'):
                text += f"\n  📝 {item['admin_notes']}"
            
            text += "\n"
        
        text += f"\n💰 جمع: {total_price:,.0f} تومان"
        
        if discount_amount > 0:
            text += f"\n🎁 تخفیف: {discount_amount:,.0f} تومان"
            text += f"\n💳 نهایی: {final_price:,.0f} تومان"
        
        text += f"\n\n📅 تاریخ: {format_jalali_datetime(created_at)}"
        text += f"\n⏰ انقضا: {format_jalali_datetime(expires_at)}"
        
        await update.message.reply_text(
            text,
            reply_markup=order_confirmation_keyboard(order_id),
            parse_mode='Markdown'
        )


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تایید سفارش توسط ادمین
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer("✅ سفارش تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    # دریافت سفارش
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
        iban=IBAN_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message)
    
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد - در انتظار پرداخت"
    )
    
    logger.info(f"✅ سفارش {order_id} توسط ادمین تایید شد")


async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نمایش آیتم‌ها برای حذف
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer(
            "⏰ این سفارش منقضی شده است!\n\n"
            "💡 نیازی به رد کردن نیست.",
            show_alert=True
        )
        logger.info(f"⚠️ تلاش برای رد سفارش منقضی {order_id}")
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    
    text = "🗑 **حذف آیتم از سفارش**\n\n"
    text += f"📋 سفارش #{order_id}\n\n"
    text += "کدام محصول را می‌خواهید حذف کنید؟\n\n"
    
    for idx, item in enumerate(items):
        text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
        text += f"   {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            text += f"\n   📝 {item['admin_notes']}"
        
        text += f" - {item['price']:,.0f} تومان\n\n"
    
    text += f"💳 جمع کل: {final_price:,.0f} تومان"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=order_items_removal_keyboard(order_id, items)
    )


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
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer(
            "⏰ این سفارش منقضی شده است!\n\n"
            "💡 نمی‌توان آیتمی حذف کرد.",
            show_alert=True
        )
        logger.info(f"⚠️ تلاش برای حذف آیتم از سفارش منقضی {order_id}")
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    
    # چک آیتم آخر
    if len(items) <= 1:
        await query.answer(
            "⚠️ نمی‌توانید آخرین آیتم را حذف کنید!\n\n"
            "💡 اگر می‌خواهید کل سفارش رد بشه، از دکمه 'رد کامل' استفاده کنید.",
            show_alert=True
        )
        return
    
    # حذف آیتم
    removed_item = items.pop(item_index)
    
    # محاسبه مجدد
    new_total = sum(item['price'] for item in items)
    new_discount = 0
    new_final = new_total
    
    if discount_code:
        discount_info = db.get_discount(discount_code)
        if discount_info:
            discount_type = discount_info[2]
            discount_value = discount_info[3]
            min_purchase = discount_info[4]
            max_discount = discount_info[5]
            
            if new_total >= min_purchase:
                if discount_type == 'percentage':
                    new_discount = new_total * (discount_value / 100)
                    if max_discount and new_discount > max_discount:
                        new_discount = max_discount
                else:
                    new_discount = discount_value
                
                new_final = new_total - new_discount
    
    # بروزرسانی
    try:
        with db.transaction() as cursor:
            cursor.execute("""
                UPDATE orders 
                SET items = ?, total_price = ?, discount_amount = ?, final_price = ? 
                WHERE id = ?
            """, (json.dumps(items, ensure_ascii=False), new_total, new_discount, new_final, order_id))
        
        logger.info(f"✅ آیتم از سفارش {order_id} حذف شد")
    except Exception as e:
        logger.error(f"❌ خطا در حذف آیتم از سفارش {order_id}: {e}")
        await query.answer("❌ خطا در حذف آیتم!", show_alert=True)
        return
    
    text = "✅ **آیتم حذف شد!**\n\n"
    text += f"❌ حذف شد: {removed_item['product']} - {removed_item['pack']}\n\n"
    text += "📋 آیتم‌های باقی‌مانده:\n\n"
    
    for idx, item in enumerate(items):
        text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
        text += f"   {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            text += f"\n   📝 {item['admin_notes']}"
        
        text += f" - {item['price']:,.0f} تومان\n\n"
    
    text += f"💳 جمع جدید: {new_final:,.0f} تومان\n\n"
    
    if len(items) == 1:
        text += "⚠️ **این آخرین آیتم است!**\n"
        text += "برای رد کامل سفارش از دکمه زیر استفاده کنید.\n\n"
    else:
        text += "می‌خواهید آیتم دیگری حذف کنید؟"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=order_items_removal_keyboard(order_id, items)
    )


async def reject_full_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    رد کامل سفارش
    ✅ FIX: چک expire اضافه شد
    """
    query = update.callback_query
    await query.answer("❌ سفارش کامل رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    
    # ✅ بررسی منقضی بودن
    if is_order_expired(order):
        await query.answer(
            "⏰ این سفارش منقضی شده است!\n\n"
            "💡 نیازی به رد کردن نیست.",
            show_alert=True
        )
        logger.info(f"⚠️ تلاش برای رد سفارش منقضی {order_id}")
        return
    
    db.update_order_status(order_id, OrderStatus.REJECTED)
    
    user_id = order[1]
    
    await context.bot.send_message(
        user_id,
        "❌ متأسفانه سفارش شما رد شد.\n\n"
        "💡 محصولات همچنان در سبد شما باقی هستند.\n"
        "می‌توانید تغییرات لازم را اعمال کرده و دوباره سفارش دهید.\n\n"
        "📞 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
        reply_markup=user_main_keyboard()
    )
    
    await query.edit_message_text(
        query.message.text + "\n\n❌ رد شد (کامل)"
    )
    
    logger.info(f"❌ سفارش {order_id} توسط ادمین رد شد")


async def back_to_order_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به بررسی سفارش"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
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
        iban=IBAN_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message, parse_mode='Markdown')
    
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد با تغییرات - در انتظار پرداخت"
    )
    
    logger.info(f"✅ سفارش {order_id} با تغییرات توسط ادمین تایید شد")


# ==================== PAYMENT HANDLERS ====================

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
        iban=IBAN_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message)
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ رد شد - منتظر رسید جدید"
    )
    
    logger.info(f"❌ رسید سفارش {order_id} رد شد")
