"""
مدیریت سفارشات و پرداخت‌ها
✅ FIX: مدیریت خطاها و نمایش صحیح سفارشات
"""
import json
import jdatetime
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from logger import log_payment, log_admin_action, log_error
from config import ADMIN_ID, MESSAGES, CARD_NUMBER, CARD_HOLDER
from keyboards import (
    order_confirmation_keyboard, 
    payment_confirmation_keyboard, 
    user_main_keyboard,
    order_items_removal_keyboard
)
import logging

logger = logging.getLogger(__name__)


def format_jalali_datetime(dt_str):
    """تبدیل تاریخ میلادی به شمسی"""
    try:
        if isinstance(dt_str, str):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = dt_str
        
        jalali = jdatetime.datetime.fromgregorian(datetime=dt)
        return jalali.strftime('%Y/%m/%d %H:%M')
    except Exception as e:
        logger.error(f"❌ خطا در تبدیل تاریخ: {e}")
        return str(dt_str)


def get_order_status_emoji(status):
    """ایموجی وضعیت سفارش"""
    status_map = {
        'pending': '⏳',
        'waiting_payment': '💳',
        'receipt_sent': '📤',
        'payment_confirmed': '✅',
        'confirmed': '✅',
        'rejected': '❌',
        'expired': '⏰'
    }
    return status_map.get(status, '❓')


def get_order_status_text(status):
    """متن وضعیت سفارش"""
    status_map = {
        'pending': 'در انتظار تایید',
        'waiting_payment': 'در انتظار پرداخت',
        'receipt_sent': 'رسید ارسال شده',
        'payment_confirmed': 'تایید شده',
        'confirmed': 'تایید شده',
        'rejected': 'رد شده',
        'expired': 'منقضی شده'
    }
    return status_map.get(status, 'نامشخص')


def is_order_expired(order):
    """بررسی منقضی بودن سفارش"""
    try:
        # ✅ FIX: چک کردن طول order
        if not order or len(order) < 12:
            logger.warning(f"⚠️ Order incomplete: {order}")
            return False
        
        expires_at = order[11]  # فیلد expires_at
        if not expires_at:
            return False
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        return datetime.now() > expires_at
    except Exception as e:
        logger.error(f"❌ خطا در بررسی انقضا: {e}")
        return False


def create_order_action_keyboard(order_id, status, is_expired):
    """
    🆕 ساخت دکمه‌های دینامیک بر اساس وضعیت سفارش
    """
    keyboard = []
    
    # 🔴 سفارشات تکمیل شده → بدون دکمه
    if status in ['payment_confirmed', 'confirmed']:
        return None
    
    # 🟡 سفارشات منقضی شده → فقط دکمه حذف
    if is_expired:
        keyboard.append([
            InlineKeyboardButton("🗑 حذف سفارش", callback_data=f"delete_order:{order_id}")
        ])
    
    # 🟢 سفارش در مرحله پرداخت
    elif status == 'waiting_payment':
        keyboard.append([
            InlineKeyboardButton("💳 ادامه پرداخت", callback_data=f"continue_payment:{order_id}")
        ])
        keyboard.append([
            InlineKeyboardButton("🗑 حذف سفارش", callback_data=f"delete_order:{order_id}")
        ])
    
    # 🟠 رسید ارسال شده → منتظر تایید ادمین
    elif status == 'receipt_sent':
        keyboard.append([
            InlineKeyboardButton("⏳ منتظر تایید ادمین...", callback_data=f"waiting:{order_id}")
        ])
    
    # 🔵 در انتظار تایید اولیه
    elif status == 'pending':
        keyboard.append([
            InlineKeyboardButton("⏳ منتظر بررسی ادمین...", callback_data=f"waiting:{order_id}")
        ])
    
    # 🔴 رد شده → فقط دکمه حذف
    elif status == 'rejected':
        keyboard.append([
            InlineKeyboardButton("🗑 حذف سفارش", callback_data=f"delete_order:{order_id}")
        ])
    
    return InlineKeyboardMarkup(keyboard) if keyboard else None


def parse_order_safely(order):
    """
    🆕 تابع امن برای خواندن سفارش
    ✅ FIX: چک کردن تمام فیلدها قبل از استفاده
    """
    try:
        if not order:
            logger.error("❌ Order is None!")
            return None
        
        # ✅ چک کردن تعداد فیلدها
        if len(order) < 12:
            logger.error(f"❌ Order has only {len(order)} fields, expected 12!")
            logger.error(f"Order data: {order}")
            return None
        
        # ✅ Unpack امن
        order_data = {
            'id': order[0],
            'user_id': order[1],
            'items_json': order[2],
            'total_price': order[3],
            'discount_amount': order[4],
            'final_price': order[5],
            'discount_code': order[6],
            'status': order[7],
            'receipt': order[8],
            'shipping_method': order[9],
            'created_at': order[10],
            'expires_at': order[11]
        }
        
        # ✅ چک JSON معتبر
        try:
            items = json.loads(order_data['items_json'])
            order_data['items'] = items
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in order {order_data['id']}: {e}")
            return None
        
        return order_data
    
    except Exception as e:
        logger.error(f"❌ خطا در parse_order_safely: {e}", exc_info=True)
        return None


async def view_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🆕 نمایش سفارشات کاربر با تاریخ شمسی و دکمه‌های دینامیک
    ✅ FIX: مدیریت کامل خطاها
    """
    try:
        user_id = update.effective_user.id
        db = context.bot_data.get('db')
        
        if not db:
            logger.error("❌ Database not found in context!")
            await update.message.reply_text(
                "❌ خطای سیستمی! لطفاً با پشتیبانی تماس بگیرید.",
                reply_markup=user_main_keyboard()
            )
            return
        
        # ✅ دریافت سفارشات
        orders = db.get_user_orders(user_id)
        
        if not orders:
            await update.message.reply_text(
                "📭 شما هنوز سفارشی ثبت نکرده‌اید.",
                reply_markup=user_main_keyboard()
            )
            return
        
        await update.message.reply_text(f"📋 شما {len(orders)} سفارش دارید:")
        
        # ✅ پردازش هر سفارش با Try-Except جداگانه
        for order in orders:
            try:
                # ✅ Parse امن
                order_data = parse_order_safely(order)
                
                if not order_data:
                    # ⚠️ اگر سفارش خراب بود، پیام ارور بده
                    await update.message.reply_text(
                        f"⚠️ خطا در نمایش سفارش #{order[0] if order and len(order) > 0 else '???'}\n\n"
                        f"لطفاً دستی از دیتابیس بررسی کنید."
                    )
                    log_error("OrderDisplay", f"Failed to parse order: {order}")
                    continue
                
                # بررسی منقضی بودن
                expired = is_order_expired(order)
                actual_status = 'expired' if expired and order_data['status'] not in ['payment_confirmed', 'confirmed'] else order_data['status']
                
                # ساخت متن سفارش
                text = f"📋 **سفارش #{order_data['id']}**\n\n"
                text += f"📅 تاریخ: {format_jalali_datetime(order_data['created_at'])}\n"
                
                # 🆕 نمایش تاریخ انقضا فقط برای سفارشات ناتمام
                if order_data['expires_at'] and order_data['status'] not in ['payment_confirmed', 'confirmed', 'rejected']:
                    text += f"⏰ تاریخ انقضا: {format_jalali_datetime(order_data['expires_at'])}\n"
                    if expired:
                        text += "⚠️ این سفارش منقضی شده است!\n"
                
                text += f"📊 وضعیت: {get_order_status_emoji(actual_status)} {get_order_status_text(actual_status)}\n\n"
                
                text += "🛍 محصولات:\n"
                for item in order_data['items']:
                    text += f"▫️ {item.get('product', 'نامشخص')} - {item.get('pack', 'نامشخص')}\n"
                    text += f"   تعداد: {item.get('quantity', 0)} عدد\n"
                
                text += f"\n💰 مبلغ کل: {order_data['total_price']:,.0f} تومان\n"
                
                if order_data['discount_amount'] > 0:
                    text += f"🎁 تخفیف: {order_data['discount_amount']:,.0f} تومان\n"
                    text += f"💳 مبلغ نهایی: {order_data['final_price']:,.0f} تومان\n"
                
                if order_data['shipping_method']:
                    shipping_names = {
                        'terminal': 'ترمینال 🚌',
                        'barbari': 'باربری 🚚',
                        'tipax': 'تیپاکس 📦',
                        'chapar': 'چاپار 🏃'
                    }
                    text += f"📦 نحوه ارسال: {shipping_names.get(order_data['shipping_method'], order_data['shipping_method'])}\n"
                
                # 🆕 ساخت دکمه‌های دینامیک
                keyboard = create_order_action_keyboard(order_data['id'], actual_status, expired)
                
                await update.message.reply_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            
            except Exception as e:
                # ✅ لاگ خطا و ادامه به سفارش بعدی
                logger.error(f"❌ خطا در نمایش سفارش: {e}", exc_info=True)
                try:
                    order_id = order[0] if order and len(order) > 0 else '???'
                    await update.message.reply_text(
                        f"⚠️ خطا در نمایش سفارش #{order_id}\n\n"
                        f"لطفاً دستی از دیتابیس بررسی کنید."
                    )
                except:
                    pass
                continue
    
    except Exception as e:
        logger.error(f"❌ خطای کلی در view_user_orders: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.",
                reply_markup=user_main_keyboard()
            )
        except:
            pass


async def handle_continue_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🆕 ادامه فرآیند پرداخت"""
    query = update.callback_query
    await query.answer()
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.edit_message_text("❌ سفارش یافت نشد!")
            return
        
        # بررسی منقضی بودن
        if is_order_expired(order):
            await query.edit_message_text(
                "⏰ این سفارش منقضی شده است!\n\n"
                "💡 می‌توانید آن را حذف کنید و سفارش جدیدی ثبت کنید."
            )
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            await query.edit_message_text("❌ خطا در خواندن سفارش!")
            return
        
        message = MESSAGES["order_confirmed"].format(
            amount=f"{order_data['final_price']:,.0f}",
            card=CARD_NUMBER,
            holder=CARD_HOLDER
        )
        
        await query.edit_message_text(
            f"💳 **ادامه پرداخت سفارش #{order_id}**\n\n{message}",
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در handle_continue_payment: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def handle_delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🆕 حذف سفارش توسط کاربر"""
    query = update.callback_query
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        
        # بررسی مالکیت
        order = db.get_order(order_id)
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            await query.answer("❌ خطا در خواندن سفارش!", show_alert=True)
            return
        
        if order_data['user_id'] != update.effective_user.id:
            await query.answer("❌ شما مجاز به حذف این سفارش نیستید!", show_alert=True)
            return
        
        # بررسی وضعیت - جلوگیری از حذف سفارشات تکمیل شده
        if order_data['status'] in ['payment_confirmed', 'confirmed']:
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
        else:
            await query.answer("❌ خطا در حذف سفارش!", show_alert=True)
    
    except Exception as e:
        logger.error(f"❌ خطا در handle_delete_order: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def send_order_to_admin(context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """ارسال سفارش به ادمین"""
    try:
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            logger.error(f"❌ Order {order_id} not found!")
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            logger.error(f"❌ Failed to parse order {order_id}")
            return
        
        user = db.get_user(order_data['user_id'])
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        text = f"🆕 سفارش جدید #{order_data['id']}\n\n"
        text += f"👤 کاربر: {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 تلفن: {phone}\n"
        text += f"📍 آدرس: {address}\n\n"
        text += "📦 آیتم‌ها:\n"
        
        for item in order_data['items']:
            text += f"• {item.get('product', 'نامشخص')} - {item.get('pack', 'نامشخص')}\n"
            text += f"  تعداد: {item.get('quantity', 0)} عدد\n"
            
            if item.get('admin_notes'):
                text += f"  📝 توضیحات: {item['admin_notes']}\n"
            
            text += f"  قیمت: {item.get('price', 0):,.0f} تومان\n\n"
        
        text += f"💰 جمع کل: {order_data['total_price']:,.0f} تومان\n"
        
        if order_data['discount_amount'] > 0:
            text += f"🎁 تخفیف: {order_data['discount_amount']:,.0f} تومان\n"
            if order_data['discount_code']:
                text += f"🎫 کد تخفیف: {order_data['discount_code']}\n"
            text += f"💳 مبلغ نهایی: {order_data['final_price']:,.0f} تومان\n"
        
        text += f"\n📅 تاریخ: {format_jalali_datetime(order_data['created_at'])}\n"
        text += f"⏰ انقضا: {format_jalali_datetime(order_data['expires_at'])}"
        
        await context.bot.send_message(
            ADMIN_ID,
            text,
            reply_markup=order_confirmation_keyboard(order_data['id'])
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در send_order_to_admin: {e}", exc_info=True)


async def view_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سفارشات در انتظار"""
    try:
        db = context.bot_data['db']
        orders = db.get_pending_orders()
        
        if not orders:
            await update.message.reply_text("هیچ سفارش جدیدی وجود ندارد.")
            return
        
        for order in orders:
            try:
                order_data = parse_order_safely(order)
                if not order_data:
                    continue
                
                user = db.get_user(order_data['user_id'])
                
                first_name = user[2] if len(user) > 2 else "کاربر"
                username = user[1] if len(user) > 1 and user[1] else "ندارد"
                phone = user[4] if len(user) > 4 and user[4] else "ندارد"
                full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
                address = user[6] if len(user) > 6 and user[6] else "ندارد"
                
                # بررسی منقضی بودن
                expired = is_order_expired(order)
                
                text = f"📋 سفارش #{order_data['id']}\n\n"
                text += f"👤 {first_name} (@{username})\n"
                text += f"📝 نام: {full_name}\n"
                text += f"📞 {phone}\n"
                text += f"📍 {address}\n\n"
                
                if expired:
                    text += "⚠️ **این سفارش منقضی شده است!**\n\n"
                
                for item in order_data['items']:
                    text += f"• {item.get('product', 'نامشخص')} ({item.get('pack', 'نامشخص')}) - {item.get('quantity', 0)} عدد"
                    
                    if item.get('admin_notes'):
                        text += f"\n  📝 {item['admin_notes']}"
                    
                    text += "\n"
                
                text += f"\n💰 جمع: {order_data['total_price']:,.0f} تومان"
                
                if order_data['discount_amount'] > 0:
                    text += f"\n🎁 تخفیف: {order_data['discount_amount']:,.0f} تومان"
                    text += f"\n💳 نهایی: {order_data['final_price']:,.0f} تومان"
                
                text += f"\n\n📅 تاریخ: {format_jalali_datetime(order_data['created_at'])}"
                text += f"\n⏰ انقضا: {format_jalali_datetime(order_data['expires_at'])}"
                
                await update.message.reply_text(
                    text,
                    reply_markup=order_confirmation_keyboard(order_data['id']),
                    parse_mode='Markdown'
                )
            
            except Exception as e:
                logger.error(f"❌ خطا در نمایش سفارش: {e}", exc_info=True)
                continue
    
    except Exception as e:
        logger.error(f"❌ خطا در view_pending_orders: {e}", exc_info=True)


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید سفارش توسط ادمین"""
    query = update.callback_query
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        
        # بررسی منقضی بودن
        order = db.get_order(order_id)
        if is_order_expired(order):
            await query.answer("⚠️ این سفارش منقضی شده است!", show_alert=True)
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            await query.answer("❌ خطا در خواندن سفارش!", show_alert=True)
            return
        
        db.update_order_status(order_id, 'waiting_payment')
        
        message = MESSAGES["order_confirmed"].format(
            amount=f"{order_data['final_price']:,.0f}",
            card=CARD_NUMBER,
            holder=CARD_HOLDER
        )
        
        await context.bot.send_message(order_data['user_id'], message)
        await query.answer("✅ سفارش تایید شد")
        
        await query.edit_message_text(
            query.message.text + "\n\n✅ تایید شد - در انتظار پرداخت"
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در confirm_order: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آیتم‌ها برای حذف"""
    query = update.callback_query
    await query.answer()
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            await query.answer("❌ خطا در خواندن سفارش!", show_alert=True)
            return
        
        text = "🗑 **حذف آیتم از سفارش**\n\n"
        text += f"📋 سفارش #{order_data['id']}\n\n"
        text += "کدام محصول را می‌خواهید حذف کنید؟\n\n"
        
        for idx, item in enumerate(order_data['items']):
            text += f"{idx + 1}. {item.get('product', 'نامشخص')} - {item.get('pack', 'نامشخص')}\n"
            text += f"   {item.get('quantity', 0)} عدد"
            
            if item.get('admin_notes'):
                text += f"\n   📝 {item['admin_notes']}"
            
            text += f" - {item.get('price', 0):,.0f} تومان\n\n"
        
        text += f"💳 جمع کل: {order_data['final_price']:,.0f} تومان"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=order_items_removal_keyboard(order_id, order_data['items'])
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در reject_order: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


"""
ادامه فایل order.py - قسمت دوم
"""

async def remove_item_from_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف آیتم با چک تعداد"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split(":")
        order_id = int(data[1])
        item_index = int(data[2])
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            await query.answer("❌ خطا در خواندن سفارش!", show_alert=True)
            return
        
        items = order_data['items']
        
        # چک کردن آیتم آخر
        if len(items) <= 1:
            await query.answer(
                "⚠️ نمی‌توانید آخرین آیتم را حذف کنید!\n\n"
                "💡 اگر می‌خواهید کل سفارش رد بشه، از دکمه 'رد کامل' استفاده کنید.",
                show_alert=True
            )
            return
        
        # حذف آیتم
        removed_item = items.pop(item_index)
        
        # محاسبه مجدد قیمت
        new_total = sum(item.get('price', 0) for item in items)
        
        # محاسبه مجدد تخفیف
        new_discount = 0
        new_final = new_total
        
        discount_code = order_data['discount_code']
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
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE orders 
            SET items = ?, total_price = ?, discount_amount = ?, final_price = ? 
            WHERE id = ?
        """, (json.dumps(items, ensure_ascii=False), new_total, new_discount, new_final, order_id))
        conn.commit()
        
        text = "✅ **آیتم حذف شد!**\n\n"
        text += f"❌ حذف شد: {removed_item.get('product', 'نامشخص')} - {removed_item.get('pack', 'نامشخص')}\n\n"
        text += "📋 آیتم‌های باقی‌مانده:\n\n"
        
        for idx, item in enumerate(items):
            text += f"{idx + 1}. {item.get('product', 'نامشخص')} - {item.get('pack', 'نامشخص')}\n"
            text += f"   {item.get('quantity', 0)} عدد"
            
            if item.get('admin_notes'):
                text += f"\n   📝 {item['admin_notes']}"
            
            text += f" - {item.get('price', 0):,.0f} تومان\n\n"
        
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
    
    except Exception as e:
        logger.error(f"❌ خطا در remove_item_from_order: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def reject_full_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد کامل سفارش با پیام بهتر"""
    query = update.callback_query
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        
        db.update_order_status(order_id, 'rejected')
        
        order = db.get_order(order_id)
        order_data = parse_order_safely(order)
        
        if order_data:
            await context.bot.send_message(
                order_data['user_id'],
                "❌ متأسفانه سفارش شما رد شد.\n\n"
                "💡 محصولات همچنان در سبد شما باقی هستند.\n"
                "می‌توانید تغییرات لازم را اعمال کرده و دوباره سفارش دهید.\n\n"
                "📞 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
                reply_markup=user_main_keyboard()
            )
        
        await query.answer("❌ سفارش کامل رد شد")
        await query.edit_message_text(
            query.message.text + "\n\n❌ رد شد (کامل)"
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در reject_full_order: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def back_to_order_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به بررسی سفارش"""
    query = update.callback_query
    await query.answer()
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        order_data = parse_order_safely(order)
        if not order_data:
            await query.answer("❌ خطا در خواندن سفارش!", show_alert=True)
            return
        
        user = db.get_user(order_data['user_id'])
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        text = f"📋 سفارش #{order_data['id']}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        for item in order_data['items']:
            text += f"• {item.get('product', 'نامشخص')} ({item.get('pack', 'نامشخص')}) - {item.get('quantity', 0)} عدد"
            
            if item.get('admin_notes'):
                text += f"\n  📝 {item['admin_notes']}"
            
            text += "\n"
        
        text += f"\n💰 {order_data['final_price']:,.0f} تومان"
        
        await query.edit_message_text(
            text,
            reply_markup=order_confirmation_keyboard(order_data['id'])
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در back_to_order_review: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def confirm_modified_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید سفارش با تغییرات"""
    query = update.callback_query
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        
        db.update_order_status(order_id, 'waiting_payment')
        
        order = db.get_order(order_id)
        order_data = parse_order_safely(order)
        
        if not order_data:
            await query.answer("❌ خطا در خواندن سفارش!", show_alert=True)
            return
        
        message = "✅ **سفارش شما با تغییرات تایید شد!**\n"
        message += "⚠️ مدل‌های ناموجود از فاکتور شما حذف شدند.\n\n"
        message += "📦 آیتم‌های تایید شده:\n\n"
        
        for item in order_data['items']:
            message += f"• {item.get('product', 'نامشخص')} - {item.get('pack', 'نامشخص')}\n"
            message += f"  {item.get('quantity', 0)} عدد"
            
            if item.get('admin_notes'):
                message += f"\n  📝 {item['admin_notes']}"
            
            message += f" - {item.get('price', 0):,.0f} تومان\n\n"
        
        message += f"💳 مبلغ قابل پرداخت: {order_data['final_price']:,.0f} تومان\n\n"
        message += MESSAGES["order_confirmed"].format(
            amount=f"{order_data['final_price']:,.0f}",
            card=CARD_NUMBER,
            holder=CARD_HOLDER
        )
        
        await context.bot.send_message(order_data['user_id'], message, parse_mode='Markdown')
        await query.answer("✅ سفارش با تغییرات تایید شد")
        
        await query.edit_message_text(
            query.message.text + "\n\n✅ تایید شد با تغییرات - در انتظار پرداخت"
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در confirm_modified_order: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت رسید از کاربر"""
    try:
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
        
        order_data = parse_order_safely(user_order)
        if not order_data:
            await update.message.reply_text("❌ خطا در پردازش سفارش!")
            return
        
        order_id = order_data['id']
        photo = update.message.photo[-1]
        
        db.add_receipt(order_id, photo.file_id)
        db.update_order_status(order_id, 'receipt_sent')
        
        await update.message.reply_text(MESSAGES["receipt_received"])
        
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        
        text = f"💳 رسید سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"💰 مبلغ: {order_data['final_price']:,.0f} تومان\n\n"
        
        for item in order_data['items']:
            text += f"• {item.get('product', 'نامشخص')} ({item.get('pack', 'نامشخص')}) - {item.get('quantity', 0)} عدد"
            
            if item.get('admin_notes'):
                text += f"\n  📝 {item['admin_notes']}"
            
            text += "\n"
        
        await context.bot.send_photo(
            ADMIN_ID,
            photo.file_id,
            caption=text,
            reply_markup=payment_confirmation_keyboard(order_id)
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در handle_receipt: {e}", exc_info=True)
        try:
            await update.message.reply_text("❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.")
        except:
            pass


async def view_payment_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش رسیدهای در انتظار تایید"""
    try:
        db = context.bot_data['db']
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM orders WHERE status = 'receipt_sent' ORDER BY created_at DESC"
        )
        query_result = cursor.fetchall()
        
        if not query_result:
            await update.message.reply_text("هیچ رسیدی در انتظار تایید نیست.")
            return
        
        for order in query_result:
            try:
                order_data = parse_order_safely(order)
                if not order_data:
                    continue
                
                user = db.get_user(order_data['user_id'])
                
                first_name = user[2] if len(user) > 2 else "کاربر"
                username = user[1] if len(user) > 1 and user[1] else "ندارد"
                
                text = f"💳 رسید سفارش #{order_data['id']}\n\n"
                text += f"👤 {first_name} (@{username})\n"
                text += f"💰 {order_data['final_price']:,.0f} تومان\n\n"
                
                for item in order_data['items']:
                    text += f"• {item.get('product', 'نامشخص')} ({item.get('pack', 'نامشخص')}) - {item.get('quantity', 0)} عدد"
                    
                    if item.get('admin_notes'):
                        text += f"\n  📝 {item['admin_notes']}"
                    
                    text += "\n"
                
                if order_data['receipt']:
                    await update.message.reply_photo(
                        order_data['receipt'],
                        caption=text,
                        reply_markup=payment_confirmation_keyboard(order_data['id'])
                    )
            
            except Exception as e:
                logger.error(f"❌ خطا در نمایش رسید: {e}", exc_info=True)
                continue
    
    except Exception as e:
        logger.error(f"❌ خطا در view_payment_receipts: {e}", exc_info=True)


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید پرداخت توسط ادمین"""
    query = update.callback_query
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        
        db.update_order_status(order_id, 'payment_confirmed')
        
        order = db.get_order(order_id)
        order_data = parse_order_safely(order)
        
        if order_data:
            log_payment(order_id, order_data['user_id'], "confirmed")
            
            from keyboards import shipping_method_keyboard
            
            await context.bot.send_message(
                order_data['user_id'],
                "✅ رسید شما تایید شد!\n\n"
                "📦 لطفاً نحوه ارسال خود را انتخاب کنید:",
                reply_markup=shipping_method_keyboard()
            )
            
            context.bot_data[f'pending_shipping_{order_data["user_id"]}'] = order_id
        
        await query.answer("✅ پرداخت تایید شد")
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ تایید شد - منتظر انتخاب نحوه ارسال"
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در confirm_payment: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)


async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد پرداخت توسط ادمین"""
    query = update.callback_query
    
    try:
        order_id = int(query.data.split(":")[1])
        db = context.bot_data['db']
        
        db.update_order_status(order_id, 'waiting_payment')
        
        order = db.get_order(order_id)
        order_data = parse_order_safely(order)
        
        if order_data:
            message = MESSAGES["payment_rejected"] + "\n\n"
            message += MESSAGES["order_confirmed"].format(
                amount=f"{order_data['final_price']:,.0f}",
                card=CARD_NUMBER,
                holder=CARD_HOLDER
            )
            
            await context.bot.send_message(order_data['user_id'], message)
        
        await query.answer("❌ رسید رد شد")
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ رد شد - منتظر رسید جدید"
        )
    
    except Exception as e:
        logger.error(f"❌ خطا در reject_payment: {e}", exc_info=True)
        await query.answer("❌ خطایی رخ داد!", show_alert=True)
