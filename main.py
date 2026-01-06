"""
ربات فروشگاه مانتو تلگرام

"""
import logging
import signal
import sys
import time
from datetime import time as datetime_time, datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    TypeHandler,
    ConversationHandler,
    filters,
    JobQueue
)

# ایمپورت ماژول‌های پروژه
from config import BOT_TOKEN, ADMIN_ID
from database import Database
from telegram.ext import ContextTypes
from logger import (
    bot_logger, 
    log_startup, 
    log_shutdown, 
    log_user_action,
    log_error
)

from rate_limiter import rate_limiter
from states import *

# 🆕 ایمپورت ماژول‌های جدید
from health_check import HealthChecker
from error_handler import EnhancedErrorHandler
from cache_manager import cache_manager, DatabaseCache
from admin_dashboard import (
    admin_dashboard,
    handle_dashboard_callback
)

# تنظیم لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context):
    """هندلر دستور /start"""
    user_id = update.effective_user.id
    
    from handlers.admin import admin_start
    from handlers.user import user_start
    
    if user_id == ADMIN_ID:
        await admin_start(update, context)
    else:
        await user_start(update, context)


async def handle_text_messages(update: Update, context):
    """مدیریت پیام‌های متنی"""
    text = update.message.text
    user_id = update.effective_user.id
    
    from handlers.admin import add_product_start, list_products, show_statistics
    from handlers.user import view_cart, view_my_address, contact_us
    from handlers.discount import discount_menu
    from handlers.broadcast import broadcast_start
    from backup_scheduler import manual_backup
    from handlers.analytics import send_analytics_menu
    
    # 🆕 ایمپورت توابع جدید
    from handlers.order import view_user_orders
    
    # دستورات ادمین
    if user_id == ADMIN_ID:
        if text == "➕ افزودن محصول":
            return await add_product_start(update, context)
        elif text == "📦 لیست محصولات":
            return await list_products(update, context)
        elif text == "📋 سفارشات جدید":
            # 🔥 FIX: استفاده از تابع جدید
            return await view_new_orders(update, context)
        elif text == "💳 تایید پرداخت‌ها":
            return await view_payment_receipts_only(update, context)
        elif text == "🎁 مدیریت تخفیف‌ها":
            return await discount_menu(update, context)
        elif text == "📢 پیام همگانی":
            return await broadcast_start(update, context)
        elif text == "💾 بکاپ دستی":
            return await manual_backup(update, context)
        elif text == "📊 آمار":
            return await show_statistics(update, context)
        elif text == "📈 گزارش‌های تحلیلی":
            return await send_analytics_menu(update, context)
        elif text == "🎛 داشبورد":
            return await admin_dashboard(update, context)
        elif text == "🧹 پاکسازی دیتابیس":
            return await manual_cleanup(update, context)
    
    # دستورات کاربر
    if text == "🛒 سبد خرید":
        await view_cart(update, context)
    elif text == "📦 سفارشات من":
        await view_user_orders(update, context)
    elif text == "📍 آدرس ثبت شده من":
        await view_my_address(update, context)
    elif text == "📞 تماس با ما":
        await contact_us(update, context)
    elif text == "ℹ️ راهنما":
        await update.message.reply_text(
            "📚 راهنمای استفاده:\n\n"
            "1️⃣ از کانال ما محصولات را مشاهده کنید: @manto_omdeh_erfan\n"
            "2️⃣ روی دکمه پک مورد نظر کلیک کنید\n"
            "3️⃣ هر بار کلیک = 1 پک به سبد اضافه می‌شود\n"
            "4️⃣ بعد تمام شدن، روی 'سبد خرید' کلیک کنید\n"
            "5️⃣ اگر کد تخفیف دارید وارد کنید\n"
            "6️⃣ سفارش خود را نهایی کنید\n"
            "7️⃣ بعد از تایید، مبلغ را واریز کنید\n"
            "8️⃣ رسید را ارسال کنید\n"
            "9️⃣ سفارش شما ارسال می‌شود! 🎉"
        )


async def view_new_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🆕 نمایش سفارشات جدید برای ادمین
    شامل: pending + receipt_sent (فوری‌ترین)
    """
    from handlers.admin import is_admin
    from keyboards import admin_main_keyboard
    
    if not await is_admin(update.effective_user.id):
        return
    
    db = context.bot_data['db']
    conn = db._get_conn()
    cursor = conn.cursor()
    
    # دریافت سفارشات نیازمند بررسی
    cursor.execute("""
        SELECT * FROM orders 
        WHERE status IN ('pending', 'receipt_sent')
        AND datetime(expires_at) > datetime('now')
        ORDER BY 
            CASE status
                WHEN 'receipt_sent' THEN 1
                WHEN 'pending' THEN 2
            END,
            created_at DESC
    """)
    
    orders = cursor.fetchall()
    
    if not orders:
        await update.message.reply_text(
            "✅ هیچ سفارش جدیدی برای بررسی وجود ندارد!",
            reply_markup=admin_main_keyboard()
        )
        return
    
    # شمارش
    pending_count = sum(1 for o in orders if o[7] == 'pending')
    receipt_count = sum(1 for o in orders if o[7] == 'receipt_sent')
    
    summary = f"📋 **سفارشات جدید** ({len(orders)} سفارش)\n\n"
    
    if receipt_count > 0:
        summary += f"🔥 {receipt_count} رسید منتظر تایید (فوری!)\n"
    if pending_count > 0:
        summary += f"⏳ {pending_count} سفارش منتظر بررسی اولیه\n"
    
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    # نمایش سفارشات
    from handlers.order import (
        format_jalali_datetime,
        is_order_expired,
        order_confirmation_keyboard,
        payment_confirmation_keyboard
    )
    import json
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt_photo, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        # متن سفارش
        if status == 'receipt_sent':
            text = f"💳 **رسید سفارش #{order_id}** (فوری!)\n\n"
        else:
            text = f"📋 **سفارش #{order_id}**\n\n"
        
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        text += "📦 آیتم‌ها:\n"
        for item in items:
            text += f"• {item['product']} - {item['pack']}\n"
            text += f"  تعداد: {item['quantity']} عدد\n"
            if item.get('admin_notes'):
                text += f"  📝 {item['admin_notes']}\n"
        
        text += f"\n💰 جمع: {total_price:,.0f} تومان\n"
        
        if discount_amount > 0:
            text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
            if discount_code:
                text += f"🎫 کد: {discount_code}\n"
            text += f"💳 نهایی: {final_price:,.0f} تومان\n"
        
        text += f"\n📅 {format_jalali_datetime(created_at)}\n"
        text += f"⏰ انقضا: {format_jalali_datetime(expires_at)}"
        
        # ارسال بسته به وضعیت
        if status == 'receipt_sent' and receipt_photo:
            await update.message.reply_photo(
                receipt_photo,
                caption=text,
                parse_mode='Markdown',
                reply_markup=payment_confirmation_keyboard(order_id)
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=order_confirmation_keyboard(order_id)
            )


async def view_payment_receipts_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🆕 نمایش فقط رسیدهای منتظر تایید
    """
    from handlers.admin import is_admin
    from keyboards import admin_main_keyboard
    
    if not await is_admin(update.effective_user.id):
        return
    
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
        await update.message.reply_text(
            "✅ هیچ رسیدی منتظر تایید نیست!",
            reply_markup=admin_main_keyboard()
        )
        return
    
    await update.message.reply_text(f"💳 {len(orders)} رسید منتظر تایید:")
    
    from handlers.order import format_jalali_datetime, payment_confirmation_keyboard
    import json
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt_photo, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        
        text = f"💳 **رسید سفارش #{order_id}**\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"💰 {final_price:,.0f} تومان\n\n"
        
        for item in items:
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد\n"
        
        text += f"\n📅 {format_jalali_datetime(created_at)}"
        
        if receipt_photo:
            await update.message.reply_photo(
                receipt_photo,
                caption=text,
                parse_mode='Markdown',
                reply_markup=payment_confirmation_keyboard(order_id)
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=payment_confirmation_keyboard(order_id)
            )


async def handle_photos(update: Update, context):
    """مدیریت عکس‌ها (رسیدها)"""
    from handlers.order import handle_receipt
    await handle_receipt(update, context)


async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🆕 پاکسازی دستی توسط ادمین"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ شما دسترسی ندارید!")
        return
    
    await update.message.reply_text("🧹 در حال پاکسازی دیتابیس...")
    
    try:
        db = context.bot_data['db']
        report = db.cleanup_old_orders(days_old=7)
        
        if report['success']:
            message = (
                "✅ **پاکسازی موفقیت‌آمیز بود!**\n\n"
                f"🗑 تعداد حذف شده: {report['deleted_count']} سفارش\n"
                f"📅 سفارشات قدیمی‌تر از: {report['days_old']} روز\n\n"
                f"📊 سفارشات تکمیل شده حفظ شدند.\n"
                f"🔥 فقط سفارشات رد شده و منقضی شده حذف شدند."
            )
        else:
            message = f"❌ خطا در پاکسازی:\n{report.get('error', 'خطای نامشخص')}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی دستی: {e}")
        await update.message.reply_text(f"❌ خطا رخ داد: {str(e)}")


async def scheduled_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """🆕 پاکسازی زمان‌بندی شده (خودکار)"""
    try:
        logger.info("🧹 شروع پاکسازی خودکار...")
        
        db = context.bot_data['db']
        report = db.cleanup_old_orders(days_old=7)
        
        if report['success'] and report['deleted_count'] > 0:
            message = (
                "🤖 **گزارش پاکسازی خودکار**\n\n"
                f"🗑 تعداد حذف شده: {report['deleted_count']} سفارش\n"
                f"📅 سفارشات قدیمی‌تر از: {report['days_old']} روز\n"
                f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"✅ پاکسازی با موفقیت انجام شد."
            )
            
            await context.bot.send_message(
                ADMIN_ID,
                message,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ پاکسازی خودکار موفق: {report['deleted_count']} سفارش حذف شد")
        else:
            logger.info("ℹ️ هیچ سفارش قدیمی برای حذف وجود نداشت")
            
    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی خودکار: {e}")
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ خطا در پاکسازی خودکار:\n{str(e)}"
            )
        except:
            pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    error = context.error
    
    enhanced_error_handler = context.bot_data.get('error_handler')
    
    if enhanced_error_handler:
        user_id = update.effective_user.id if update and update.effective_user else None
        
        try:
            await enhanced_error_handler.handle_error(
                error=error,
                context=context,
                user_id=user_id,
                extra_info={'update_type': type(update).__name__ if update else 'None'}
            )
        except Exception as e:
            logger.error(f"❌ Error in error handler: {e}", exc_info=True)
    else:
        logger.error(f"❌ Exception while handling update {update}:", exc_info=error)
        
        if update and update.effective_user:
            try:
                await context.bot.send_message(
                    update.effective_user.id,
                    "❌ متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید."
                )
            except:
                pass


async def global_rate_limit_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی محدودیت سراسری"""
    if not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        return
    
    allowed, remaining_time = rate_limiter.check_rate_limit(
        user_id,
        max_requests=20,
        window_seconds=60
    )
    
    if not allowed:
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        
        if minutes > 0:
            wait_msg = f"{minutes} دقیقه و {seconds} ثانیه"
        else:
            wait_msg = f"{seconds} ثانیه"
        
        try:
            if update.message:
                await update.message.reply_text(
                    f"🛑 **محدودیت درخواست!**\n\n"
                    f"⏰ لطفاً {wait_msg} صبر کنید.\n\n"
                    f"💡 محدودیت: 20 درخواست در دقیقه",
                    parse_mode='Markdown'
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    f"⚠️ لطفاً {wait_msg} صبر کنید",
                    show_alert=True
                )
        except Exception as e:
            logger.error(f"❌ Rate limit error: {e}")
        
        return


def setup_signal_handlers(application, db):
    """تنظیم signal handlers برای Graceful Shutdown"""
    def signal_handler(sig, frame):
        logger.info(f"🛑 Received signal {sig}, shutting down gracefully...")
        
        try:
            if db:
                db.close()
                logger.info("✅ Database closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing database: {e}")
        
        log_shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("✅ Signal handlers registered")


def main():
    """تابع اصلی"""
    log_startup()
    
    start_time = time.time()
    
    # Import توابع
    from handlers.admin import (
        add_product_start, product_name_received, product_desc_received,
        product_photo_received, add_pack_start, pack_name_received,
        pack_quantity_received, pack_price_received,
        get_channel_link, delete_product, admin_start
    )
    
    from handlers.admin_extended import (
        edit_product_menu, edit_product_name_start, edit_product_name_received,
        edit_product_desc_start, edit_product_desc_received,
        edit_product_photo_start, edit_product_photo_received,
        view_packs_with_edit, edit_pack_start, edit_pack_name_received,
        edit_pack_quantity_received, edit_pack_price_received,
        delete_pack_confirm, edit_in_channel, back_to_product
    )
    
    from handlers.admin_pack_management import (
        manage_packs_menu,
        confirm_delete_pack,
        delete_pack_final
    )
    
    from handlers.user import (
        finalize_order_start, full_name_received, address_text_received, 
        phone_number_received, use_old_address,
        use_new_address, handle_pack_selection, view_cart,
        remove_from_cart, clear_cart, handle_shipping_selection,
        final_confirm_order, final_edit_order, edit_address,
        back_to_packs, user_start, confirm_user_info, edit_user_info_for_order,
        cart_increase, cart_decrease
    )
    
    from handlers.user_discount import (
        apply_discount_start,
        discount_code_entered
    )
    
    from handlers.order import (
        confirm_order, reject_order, confirm_payment, reject_payment,
        remove_item_from_order, reject_full_order, back_to_order_review,
        confirm_modified_order,
        handle_continue_payment,
        handle_delete_order
    )
    
    from handlers.order_management import (
        increase_item_quantity,
        decrease_item_quantity,
        edit_item_quantity_start,
        edit_item_quantity_received,
        edit_item_notes_received,
        skip_item_notes,
        cancel_item_edit,
        EDIT_ITEM_NOTES
    )
    
    from handlers.discount import (
        create_discount_start, discount_code_received, discount_type_selected,
        discount_value_received, discount_min_purchase_received,
        discount_max_received, discount_limit_received,
        discount_start_received, discount_end_received,
        list_discounts, view_discount, toggle_discount, delete_discount
    )
    
    from handlers.broadcast import (
        broadcast_start, broadcast_message_received, 
        confirm_broadcast, cancel_broadcast
    )
    
    from handlers.analytics import handle_analytics_report, scheduled_stats_update
    
    # ایجاد دیتابیس
    db = Database()
    
    db_cache = DatabaseCache(db, cache_manager)
    health_checker = HealthChecker(db, start_time)
    enhanced_error_handler = EnhancedErrorHandler(health_checker)
    
    # ساخت اپلیکیشن
    try:
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .job_queue(JobQueue())
            .build()
        )
        logger.info("✅ Application با JobQueue ساخته شد")
    except Exception as e:
        logger.warning(f"⚠️ خطا در ساخت JobQueue: {e}")
        application = Application.builder().token(BOT_TOKEN).build()
    
    # ذخیره در bot_data
    application.bot_data['db'] = db
    application.bot_data['db_cache'] = db_cache
    application.bot_data['cache_manager'] = cache_manager
    application.bot_data['health_checker'] = health_checker
    application.bot_data['error_handler'] = enhanced_error_handler
    
    setup_signal_handlers(application, db)
    
    # اضافه کردن Global Rate Limiter
    application.add_handler(
        TypeHandler(Update, global_rate_limit_check),
        group=-1
    )
    logger.info("✅ Global rate limiter فعال شد")
    
    # راه‌اندازی بکاپ خودکار
    from backup_scheduler import setup_backup_job, setup_backup_folder
    setup_backup_folder()
    
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            setup_backup_job(application)
            logger.info("✅ بکاپ خودکار روزانه فعال شد")
        else:
            logger.warning("⚠️ JobQueue در دسترس نیست - بکاپ خودکار غیرفعال است")
    except Exception as e:
        logger.warning(f"⚠️ خطا در راه‌اندازی بکاپ خودکار: {e}")
    
    # 🆕 راه‌اندازی پاکسازی خودکار روزانه
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            application.job_queue.run_daily(
                scheduled_cleanup,
                time=datetime_time(hour=3, minute=30),
                name="cleanup_old_orders"
            )
            logger.info("✅ پاکسازی خودکار روزانه فعال شد (ساعت 3:30 صبح)")
        else:
            logger.warning("⚠️ JobQueue در دسترس نیست - پاکسازی خودکار غیرفعال است")
    except Exception as e:
        logger.warning(f"⚠️ خطا در راه‌اندازی پاکسازی خودکار: {e}")
    
    # راه‌اندازی به‌روزرسانی دوره‌ای آمار
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            application.job_queue.run_repeating(
                scheduled_stats_update,
                interval=3600,
                first=10,
                name="stats_update"
            )
            logger.info("✅ به‌روزرسانی دوره‌ای آمار فعال شد (هر 1 ساعت)")
        else:
            logger.warning("⚠️ JobQueue در دسترس نیست - به‌روزرسانی آمار غیرفعال است")
    except Exception as e:
        logger.warning(f"⚠️ خطا در راه‌اندازی به‌روزرسانی آمار: {e}")
    
    # ==================== ConversationHandler ها ====================
    
    add_product_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ افزودن محصول$"), add_product_start)],
        states={
            PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_name_received)],
            PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_desc_received)],
            PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, product_photo_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    add_pack_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_pack_start, pattern="^add_pack:")],
        states={
            PACK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_name_received)],
            PACK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_quantity_received)],
            PACK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_price_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    edit_product_name_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_product_name_start, pattern="^edit_prod_name:")],
        states={
            EDIT_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_name_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    edit_product_desc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_product_desc_start, pattern="^edit_prod_desc:")],
        states={
            EDIT_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_desc_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    edit_product_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_product_photo_
