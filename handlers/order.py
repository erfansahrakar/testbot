"""
مدیریت سفارشات و پرداخت‌ها

"""
import json
import jdatetime
import logging
import pytz
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

# Timezone تهران
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

def get_tehran_now():
    """دریافت زمان فعلی تهران"""
    return datetime.now(TEHRAN_TZ)


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
    بررسی منقضی بودن سفارش (با timezone تهران)
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
    
    # ✅ FIX: اگر expires_at بدون timezone هست، timezone تهران بهش اضافه می‌کنیم
    if expires_at.tzinfo is None:
        expires_at = TEHRAN_TZ.localize(expires_at)
    
    return get_tehran_now() > expires_at


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
        order_id, user_id_val, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
        items = json.loads(items_json)
        
        # بررسی منقضی بودن
        expired = is_order_expired(order)
        actual_status = OrderStatus.EXPIRED if expired and status not in [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.CONFIRMED] else status
        
        # ساخت متن
        text = f"📋 سفارش شماره {order_id}\n\n"
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
        
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=None)


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
            "لطفاً سفارش جدید ثبت کنید."
        )
        return
    
    final_price = order[5]
    
    message = MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        iban=IBAN_NUMBER,
        holder=CARD_HOLDER
    )
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(message, parse_mode=None)


async def handle_delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف سفارش توسط کاربر"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    if not order or order[1] != user_id:
        await query.edit_message_text("❌ سفارش یافت نشد یا متعلق به شما نیست!")
        return
    
    success = db.delete_order(order_id)
    
    if success:
        await query.edit_message_text("✅ سفارش با موفقیت حذف شد.")
        logger.info(f"🗑 سفارش {order_id} توسط کاربر {user_id} حذف شد")
    else:
        await query.edit_message_text("❌ خطا در حذف سفارش!")


# ==================== ADMIN HANDLERS ====================

async def send_order_to_admin(context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """ارسال سفارش به ادمین"""
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        logger.error(f"❌ سفارش {order_id} یافت نشد برای ارسال به ادمین")
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"🆕 سفارش جدید شماره {order_id_val}\n\n"
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
        # ✅ FIX: اضافه کردن parse_mode=None
        await context.bot.send_message(
            ADMIN_ID,
            text,
            reply_markup=order_confirmation_keyboard(order_id_val),
            parse_mode=None
        )
        logger.info(f"✅ سفارش {order_id_val} به ادمین ارسال شد")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال سفارش {order_id_val} به ادمین: {e}")


async def view_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سفارشات در انتظار تایید"""
    db = context.bot_data['db']
    
    # فقط سفارشات pending و غیر منقضی
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders 
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    all_pending = cursor.fetchall()
    
    # فیلتر سفارشات غیر منقضی
    pending_orders = [order for order in all_pending if not is_order_expired(order)]
    
    if not pending_orders:
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text("📭 سفارشی در انتظار تایید وجود ندارد.", parse_mode=None)
        return
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await update.message.reply_text(f"📋 سفارشات در انتظار تایید: {len(pending_orders)} سفارش", parse_mode=None)
    
    for order in pending_orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        # ✅ FIX: حذف # از متن برای جلوگیری از خطای parse
        text = f"📋 سفارش شماره {order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 موبایل: {phone}\n"
        text += f"📍 آدرس: {address}\n\n"
        
        text += "🛍 محصولات:\n"
        for item in items:
            text += f"• {item['product']} - {item['pack']}\n"
            text += f"  تعداد: {item['quantity']} عدد\n"
        
        text += f"\n💰 جمع کل: {total_price:,.0f} تومان\n"
        if discount_amount > 0:
            text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
            text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان\n"
        
        text += f"\n📅 تاریخ: {format_jalali_datetime(created_at)}\n"
        
        if expires_at:
            text += f"⏰ تاریخ انقضا: {format_jalali_datetime(expires_at)}"
        
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text(
            text,
            reply_markup=order_confirmation_keyboard(order_id),
            parse_mode=None
        )


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید سفارش توسط ادمین"""
    query = update.callback_query
    await query.answer("✅ سفارش تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    # ✅ بررسی منقضی بودن قبل از تایید
    order = db.get_order(order_id)
    if is_order_expired(order):
        await query.edit_message_text(
            "⏰ این سفارش منقضی شده و نمی‌توان آن را تایید کرد!\n\n"
            "سفارش باید توسط کاربر مجدداً ثبت شود."
        )
        return
    
    db.update_order_status(order_id, OrderStatus.WAITING_PAYMENT)
    log_admin_action(ADMIN_ID, f"confirm_order:{order_id}")
    
    user_id = order[1]
    final_price = order[5]
    
    message = MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        iban=IBAN_NUMBER,
        holder=CARD_HOLDER
    )
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_message(user_id, message, parse_mode=None)
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید نهایی شد و آماده پرداخت است",
        parse_mode=None
    )
    
    logger.info(f"✅ سفارش {order_id} توسط کاربر {user_id} تایید شد")


async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد سفارش توسط ادمین"""
    query = update.callback_query
    await query.answer("❌ سفارش رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, OrderStatus.REJECTED)
    log_admin_action(ADMIN_ID, f"reject_order:{order_id}")
    
    order = db.get_order(order_id)
    user_id = order[1]
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_message(
        user_id,
        MESSAGES["order_rejected"],
        parse_markup=user_main_keyboard(),
        parse_mode=None
    )
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        query.message.text + "\n\n❌ سفارش رد شد",
        parse_mode=None
    )
    
    logger.info(f"❌ سفارش {order_id} رد شد")


async def modify_order_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش صفحه مدیریت و ویرایش آیتم‌های سفارش"""
    # ✅ چک کردن query
    if not update or not update.callback_query:
        logger.error("❌ modify_order_items: update or callback_query is None")
        return
    
    query = update.callback_query
    
    # ✅ چک کردن query.data
    if not query.data:
        logger.error("❌ modify_order_items: query.data is None")
        await query.answer("❌ خطا در پردازش!", show_alert=True)
        return
    
    await query.answer()
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        # استخراج اطلاعات سفارش
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
        
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            await query.answer("❌ خطا در خواندن آیتم‌ها!", show_alert=True)
            return
        
        if not items:
            await query.answer("❌ سفارش بدون آیتم!", show_alert=True)
            return
        
        # نمایش لیست آیتم‌ها با دکمه‌های مدیریت
        text = f"📋 **مدیریت آیتم‌های سفارش #{order_id}**\n\n"
        text += "🛍 آیتم‌های سفارش:\n\n"
        
        for idx, item in enumerate(items):
            text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
            text += f"   🔢 تعداد: {item['quantity']} عدد\n"
            
            # نمایش توضیحات ادمین اگر وجود داشت
            if item.get('admin_notes'):
                text += f"   📝 توضیحات: {item['admin_notes']}\n"
            
            text += f"   💰 {item['price']:,.0f} تومان\n\n"
        
        text += f"💳 **جمع کل: {final_price:,.0f} تومان**\n\n"
        
        # پیام راهنما
        if len(items) == 1:
            text += "⚠️ **این آخرین آیتم است!**\n"
            text += "برای رد کامل سفارش از دکمه مربوطه استفاده کنید.\n\n"
        else:
            text += "💡 می‌توانید تعداد را تغییر دهید یا آیتم‌ها را حذف کنید.\n\n"
        
        text += "بعد از اعمال تغییرات، سفارش را تایید کنید."
        
        # ✅ چک کردن query.message قبل از edit
        if not query.message:
            logger.error("❌ modify_order_items: query.message is None")
            return
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=order_items_removal_keyboard(order_id, items)
        )
        
        logger.info(f"✏️ ادمین صفحه مدیریت آیتم‌های سفارش {order_id} را باز کرد")
    
    except Exception as e:
        logger.error(f"❌ Error in modify_order_items: {e}", exc_info=True)
        try:
            await query.answer("❌ خطا رخ داد!", show_alert=True)
        except:
            pass


async def handle_item_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف آیتم از سفارش"""
    query = update.callback_query
    
    try:
        _, order_id, item_idx = query.data.split(":")
        order_id = int(order_id)
        item_idx = int(item_idx)
    except:
        await query.answer("❌ خطا در پردازش!", show_alert=True)
        return
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    items = json.loads(order[2])
    
    if item_idx >= len(items):
        await query.answer("❌ آیتم نامعتبر!", show_alert=True)
        return
    
    removed_item = items.pop(item_idx)
    
    if not items:
        await query.answer("⚠️ نمی‌توان تمام آیتم‌ها را حذف کرد! برای رد کامل از دکمه مربوطه استفاده کنید.", show_alert=True)
        return
    
    # محاسبه مجدد قیمت
    total_price = sum(item['price'] * item['quantity'] for item in items)
    
    discount_amount = order[4]
    discount_code = order[6]
    
    if discount_code:
        discount = db.get_discount_by_code(discount_code)
        if discount:
            discount_type = discount[2]
            discount_value = discount[3]
            min_purchase = discount[4]
            max_discount_amount = discount[5]
            
            if total_price >= min_purchase:
                if discount_type == 'percentage':
                    discount_amount = (total_price * discount_value) / 100
                    if max_discount_amount:
                        discount_amount = min(discount_amount, max_discount_amount)
                else:
                    discount_amount = discount_value
            else:
                discount_amount = 0
                discount_code = None
    
    final_price = total_price - discount_amount
    
    # آپدیت سفارش
    with db.transaction() as cursor:
        cursor.execute("""
            UPDATE orders 
            SET items = ?, total_price = ?, discount_amount = ?, final_price = ?, discount_code = ?
            WHERE id = ?
        """, (json.dumps(items, ensure_ascii=False), total_price, discount_amount, final_price, discount_code, order_id))
    
    await query.answer(f"✅ {removed_item['product']} حذف شد", show_alert=True)
    
    # نمایش مجدد
    text = f"📋 سفارش شماره {order_id} (ویرایش شده)\n\n"
    text += "🛍 محصولات:\n"
    for item in items:
        text += f"• {item['product']} - {item['pack']}\n"
        text += f"  تعداد: {item['quantity']} عدد - {item['price']:,.0f} تومان\n"
    
    text += f"\n💰 جمع کل: {total_price:,.0f} تومان\n"
    if discount_amount > 0:
        text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
    text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان"
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        text,
        reply_markup=order_items_removal_keyboard(order_id, items),
        parse_mode=None
    )


async def handle_item_increase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزایش تعداد آیتم در سفارش"""
    query = update.callback_query
    
    try:
        _, order_id, item_idx = query.data.split(":")
        order_id = int(order_id)
        item_idx = int(item_idx)
    except:
        await query.answer("❌ خطا در پردازش!", show_alert=True)
        return
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    items = json.loads(order[2])
    
    if item_idx >= len(items):
        await query.answer("❌ آیتم نامعتبر!", show_alert=True)
        return
    
    pack_qty = items[item_idx].get('pack_quantity', 1)
    items[item_idx]['quantity'] += pack_qty
    
    # محاسبه مجدد قیمت
    total_price = sum(item['price'] * item['quantity'] for item in items)
    
    discount_amount = order[4]
    discount_code = order[6]
    
    if discount_code:
        discount = db.get_discount_by_code(discount_code)
        if discount:
            discount_type = discount[2]
            discount_value = discount[3]
            min_purchase = discount[4]
            max_discount_amount = discount[5]
            
            if total_price >= min_purchase:
                if discount_type == 'percentage':
                    discount_amount = (total_price * discount_value) / 100
                    if max_discount_amount:
                        discount_amount = min(discount_amount, max_discount_amount)
                else:
                    discount_amount = discount_value
            else:
                discount_amount = 0
                discount_code = None
    
    final_price = total_price - discount_amount
    
    # آپدیت سفارش
    with db.transaction() as cursor:
        cursor.execute("""
            UPDATE orders 
            SET items = ?, total_price = ?, discount_amount = ?, final_price = ?
            WHERE id = ?
        """, (json.dumps(items, ensure_ascii=False), total_price, discount_amount, final_price, order_id))
    
    await query.answer(f"✅ تعداد افزایش یافت", show_alert=False)
    
    # نمایش مجدد
    text = f"📋 سفارش شماره {order_id} (ویرایش شده)\n\n"
    text += "🛍 محصولات:\n"
    for item in items:
        text += f"• {item['product']} - {item['pack']}\n"
        text += f"  تعداد: {item['quantity']} عدد - {item['price']:,.0f} تومان\n"
    
    text += f"\n💰 جمع کل: {total_price:,.0f} تومان\n"
    if discount_amount > 0:
        text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
    text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان"
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        text,
        reply_markup=order_items_removal_keyboard(order_id, items),
        parse_mode=None
    )


async def handle_item_decrease(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاهش تعداد آیتم در سفارش"""
    query = update.callback_query
    
    try:
        _, order_id, item_idx = query.data.split(":")
        order_id = int(order_id)
        item_idx = int(item_idx)
    except:
        await query.answer("❌ خطا در پردازش!", show_alert=True)
        return
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    items = json.loads(order[2])
    
    if item_idx >= len(items):
        await query.answer("❌ آیتم نامعتبر!", show_alert=True)
        return
    
    pack_qty = items[item_idx].get('pack_quantity', 1)
    
    if items[item_idx]['quantity'] <= pack_qty:
        await query.answer("⚠️ تعداد نمی‌تواند کمتر از یک پک باشد! برای حذف از دکمه حذف استفاده کنید.", show_alert=True)
        return
    
    items[item_idx]['quantity'] -= pack_qty
    
    # محاسبه مجدد قیمت
    total_price = sum(item['price'] * item['quantity'] for item in items)
    
    discount_amount = order[4]
    discount_code = order[6]
    
    if discount_code:
        discount = db.get_discount_by_code(discount_code)
        if discount:
            discount_type = discount[2]
            discount_value = discount[3]
            min_purchase = discount[4]
            max_discount_amount = discount[5]
            
            if total_price >= min_purchase:
                if discount_type == 'percentage':
                    discount_amount = (total_price * discount_value) / 100
                    if max_discount_amount:
                        discount_amount = min(discount_amount, max_discount_amount)
                else:
                    discount_amount = discount_value
            else:
                discount_amount = 0
                discount_code = None
    
    final_price = total_price - discount_amount
    
    # آپدیت سفارش
    with db.transaction() as cursor:
        cursor.execute("""
            UPDATE orders 
            SET items = ?, total_price = ?, discount_amount = ?, final_price = ?
            WHERE id = ?
        """, (json.dumps(items, ensure_ascii=False), total_price, discount_amount, final_price, order_id))
    
    await query.answer(f"✅ تعداد کاهش یافت", show_alert=False)
    
    # نمایش مجدد
    text = f"📋 سفارش شماره {order_id} (ویرایش شده)\n\n"
    text += "🛍 محصولات:\n"
    for item in items:
        text += f"• {item['product']} - {item['pack']}\n"
        text += f"  تعداد: {item['quantity']} عدد - {item['price']:,.0f} تومان\n"
    
    text += f"\n💰 جمع کل: {total_price:,.0f} تومان\n"
    if discount_amount > 0:
        text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
    text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان"
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        text,
        reply_markup=order_items_removal_keyboard(order_id, items),
        parse_mode=None
    )


async def confirm_modified_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید نهایی سفارش ویرایش شده"""
    query = update.callback_query
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    # ✅ بررسی منقضی بودن
    order = db.get_order(order_id)
    if is_order_expired(order):
        await query.answer("⏰ این سفارش منقضی شده است!", show_alert=True)
        # ✅ FIX: اضافه کردن parse_mode=None
        await query.edit_message_text(
            "⏰ این سفارش منقضی شده و نمی‌توان آن را تایید کرد!",
            parse_mode=None
        )
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
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_message(user_id, message, parse_mode=None)
    
    await query.answer("✅ سفارش با تغییرات تایید شد", show_alert=True)
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد - منتظر پرداخت",
        parse_mode=None
    )


async def reject_full_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد کامل سفارش"""
    query = update.callback_query
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, OrderStatus.REJECTED)
    
    order = db.get_order(order_id)
    user_id = order[1]
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_message(
        user_id,
        MESSAGES["order_rejected"],
        reply_markup=user_main_keyboard(),
        parse_mode=None
    )
    
    await query.answer("❌ سفارش رد شد", show_alert=True)
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        "❌ سفارش به طور کامل رد شد",
        parse_mode=None
    )


async def view_payment_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش رسیدهای پرداخت برای ادمین"""
    db = context.bot_data['db']
    
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders 
        WHERE status = 'receipt_sent'
        ORDER BY created_at DESC
    """)
    orders = cursor.fetchall()
    
    if not orders:
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text("📭 رسید پرداختی برای تایید وجود ندارد.", parse_mode=None)
        return
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await update.message.reply_text(f"💳 رسیدهای در انتظار تایید: {len(orders)} رسید", parse_mode=None)
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, receipt_photo, *_ = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        
        # ✅ FIX: حذف # از متن
        text = f"💳 رسید پرداخت سفارش شماره {order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n\n"
        
        text += "🛍 محصولات:\n"
        for item in items:
            text += f"• {item['product']} - {item['pack']}\n"
            text += f"  تعداد: {item['quantity']} عدد\n"
        
        text += f"\n💰 مبلغ نهایی: {final_price:,.0f} تومان\n"
        text += f"📅 تاریخ: {format_jalali_datetime(created_at)}"
        
        if receipt_photo:
            await update.message.reply_photo(
                receipt_photo,
                caption=text,
                reply_markup=payment_confirmation_keyboard(order_id),
                parse_mode=None
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
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_message(
        user_id,
        "✅ رسید شما تایید شد!\n\n"
        "📦 لطفاً نحوه ارسال خود را انتخاب کنید:",
        reply_markup=shipping_method_keyboard(),
        parse_mode=None
    )
    
    context.bot_data[f'pending_shipping_{user_id}'] = order_id
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ تایید شد - منتظر انتخاب نحوه ارسال",
        parse_mode=None
    )
    
    logger.info(f"✅ پرداخت سفارش {order_id} تایید شد")


async def view_not_shipped_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سفارشات ارسال نشده (confirmed یا payment_confirmed، بدون shipped)"""
    db = context.bot_data['db']
    
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders 
        WHERE status IN ('payment_confirmed', 'confirmed') 
        AND (shipping_method IS NULL OR shipping_method != 'shipped')
        ORDER BY created_at DESC
    """)
    orders = cursor.fetchall()
    
    if not orders:
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text("📭 سفارشی ارسال نشده وجود نداشت.", parse_mode=None)
        return
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await update.message.reply_text(f"📦 سفارشات ارسال نشده: {len(orders)} سفارش", parse_mode=None)
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        # ✅ FIX: حذف # از متن
        text = f"📋 سفارش شماره {order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 موبایل: {phone}\n"
        text += f"📍 آدرس: {address}\n\n"
        
        text += "🛍 محصولات:\n"
        for item in items:
            text += f"• {item['product']} - {item['pack']}\n"
            text += f"  تعداد: {item['quantity']} عدد\n"
        
        text += f"\n💰 جمع کل: {total_price:,.0f} تومان\n"
        if discount_amount > 0:
            text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
            text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان\n"
        
        if shipping_method:
            text += f"\n📦 نحوه ارسال: {shipping_method}\n"
        
        text += f"\n📅 تاریخ: {format_jalali_datetime(created_at)}"
        
        from keyboards import order_shipped_keyboard
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text(
            text,
            reply_markup=order_shipped_keyboard(order_id),
            parse_mode=None
        )


async def view_shipped_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سفارشات ارسال شده"""
    db = context.bot_data['db']
    
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders 
        WHERE shipping_method = 'shipped'
        ORDER BY created_at DESC
    """)
    orders = cursor.fetchall()
    
    if not orders:
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text("📭 سفارشی ارسال شده وجود نداشت.", parse_mode=None)
        return
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await update.message.reply_text(f"✅ سفارشات ارسال شده: {len(orders)} سفارش", parse_mode=None)
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method_raw, created_at, expires_at, *_ = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        # ✅ FIX: حذف # از متن
        text = f"✅ سفارش شماره {order_id} — ارسال شده\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 موبایل: {phone}\n"
        text += f"📍 آدرس: {address}\n\n"
        
        text += "🛍 محصولات:\n"
        for item in items:
            text += f"• {item['product']} - {item['pack']}\n"
            text += f"  تعداد: {item['quantity']} عدد\n"
        
        text += f"\n💰 جمع کل: {total_price:,.0f} تومان\n"
        if discount_amount > 0:
            text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
            text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان\n"
        
        # نحوه ارسال اصلی رو ذخیره کردیم توی receipt_photo با فرمت "shipped|نحوه_ارسال"
        original_shipping = None
        if receipt and receipt.startswith("shipped|"):
            original_shipping = receipt.split("|", 1)[1]
        
        if original_shipping:
            text += f"\n📦 نحوه ارسال: {original_shipping}\n"
        
        text += f"\n📅 تاریخ: {format_jalali_datetime(created_at)}"
        
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text(text, parse_mode=None)


async def mark_order_shipped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید ارسال سفارش توسط ادمین"""
    query = update.callback_query
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    # نحوه ارسال فعلی رو قبل از تغییر ذخیره کن
    current_shipping = order[9] if order[9] else "نامشخص"
    
    # shipping_method رو به 'shipped' تغییر بده
    # نحوه ارسال اصلی رو توی receipt_photo ذخیره کن با فرمت "shipped|نحوه_ارسال"
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE orders SET shipping_method = 'shipped', receipt_photo = ? WHERE id = ?",
            (f"shipped|{current_shipping}", order_id)
        )
    
    await query.answer("✅ سفارش به عنوان ارسال شده ثبت شد!", show_alert=True)
    
    # متن پیام رو بدون دکمه بذاریم
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        query.message.text + f"\n\n✅ ارسال شد",
        parse_mode=None
    )
    
    logger.info(f"✅ سفارش {order_id} به عنوان ارسال شده ثبت شد")


async def admin_delete_not_shipped_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف سفارش ارسال نشده توسط ادمین"""
    query = update.callback_query
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    success = db.delete_order(order_id)
    
    if success:
        await query.answer("✅ سفارش حذف شد", show_alert=True)
        # ✅ FIX: اضافه کردن parse_mode=None
        await query.edit_message_text(f"🗑 سفارش شماره {order_id} حذف شد.", parse_mode=None)
        logger.info(f"🗑 سفارش {order_id} توسط ادمین حذف شد")
    else:
        await query.answer("❌ خطا در حذف سفارش!", show_alert=True)


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
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_message(user_id, message, parse_mode=None)
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ رد شد - منتظر رسید جدید",
        parse_mode=None
    )
    
    logger.info(f"❌ رسید سفارش {order_id} رد شد")


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
        # ✅ FIX: اضافه کردن parse_mode=None
        await update.message.reply_text("شما سفارش در انتظار پرداختی ندارید.", parse_mode=None)
        return
    
    order_id = user_order[0]
    photo = update.message.photo[-1]
    
    db.add_receipt(order_id, photo.file_id)
    db.update_order_status(order_id, OrderStatus.RECEIPT_SENT)
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await update.message.reply_text(MESSAGES["receipt_received"], parse_mode=None)
    
    order = db.get_order(order_id)
    items = json.loads(order[2])
    final_price = order[5]
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    
    text = f"💳 رسید سفارش شماره {order_id}\n\n"
    text += f"👤 {first_name} (@{username})\n"
    text += f"💰 مبلغ: {final_price:,.0f} تومان\n\n"
    
    for item in items:
        text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد"
        
        if item.get('admin_notes'):
            text += f"\n  📝 {item['admin_notes']}"
        
        text += "\n"
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await context.bot.send_photo(
        ADMIN_ID,
        photo.file_id,
        caption=text,
        reply_markup=payment_confirmation_keyboard(order_id),
        parse_mode=None
    )
    
    logger.info(f"📷 رسید سفارش {order_id} دریافت شد")


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
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
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
    new_total = sum(item['price'] * item['quantity'] for item in items)
    new_discount = 0
    new_final = new_total
    
    if discount_code:
        discount_info = db.get_discount_by_code(discount_code)
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
    
    text = "✅ آیتم حذف شد!\n\n"
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
        text += "⚠️ این آخرین آیتم است!\n"
        text += "برای رد کامل سفارش از دکمه زیر استفاده کنید.\n\n"
    else:
        text += "می‌خواهید آیتم دیگری حذف کنید?"
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        text,
        parse_mode=None,
        reply_markup=order_items_removal_keyboard(order_id, items)
    )


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
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"📋 سفارش شماره {order_id}\n\n"
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
    
    # ✅ FIX: اضافه کردن parse_mode=None
    await query.edit_message_text(
        text,
        parse_mode=None,
        reply_markup=order_confirmation_keyboard(order_id)
    )
