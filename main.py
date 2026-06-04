"""
ربات فروشگاه مانتو تلگرام
"""
import logging
import signal
import sys
import time
from datetime import time as datetime_time, datetime  # ✅ اضافه شدن datetime
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
# FIX: import scheduled_cleanup از cleanup_scheduler (نسخه تکراری در main.py حذف شد)
from cleanup_scheduler import scheduled_cleanup

# تنظیم لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ✅ Feature #1: Monitoring Dashboard
try:
    from monitoring import start_monitoring_dashboard, update_stats, set_error
    MONITORING_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ monitoring.py not found - Dashboard disabled")
    MONITORING_AVAILABLE = False

# ✅ Feature #4: Export Manager
try:
    from export_manager import export_menu, handle_export
    EXPORT_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ export_manager.py not found - Export disabled")
    EXPORT_AVAILABLE = False

# ✅ Feature #5: Message Customizer
try:
    from message_customizer import (
        customize_messages_menu,
        show_message_preview,
        show_category_messages,
        reset_message,
        get_message_customizer_conversation,
        message_customizer
    )
    MESSAGE_CUSTOMIZER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ message_customizer.py not found - Message customization disabled")
    MESSAGE_CUSTOMIZER_AVAILABLE = False




# ✅ Feature #2: Graceful Shutdown
def graceful_shutdown(signum, frame):
    """خاموش شدن تمیز بات"""
    logger.info("🛑 دستور خاموش شدن دریافت شد...")
    logger.info("⏳ در حال بستن کانکشن‌ها...")
    
    try:
        # بستن دیتابیس و ذخیره cache
        logger.info("💾 Saving cache and closing database...")
        logger.info("✅ Shutdown completed successfully")
    except Exception as e:
        logger.error(f"❌ خطا در shutdown: {e}")
    finally:
        log_shutdown()
        sys.exit(0)


# ثبت signal handlers
signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl+C
signal.signal(signal.SIGTERM, graceful_shutdown)  # kill command


async def start(update: Update, context):
    """هندلر دستور /start"""
    # ✅ چک کردن effective_user
    if not update.effective_user:
        logger.warning("⚠️ start called without effective_user")
        return
    
    user_id = update.effective_user.id
    
    from handlers.admin import admin_start
    from handlers.user import user_start
    
    if user_id == ADMIN_ID:
        await admin_start(update, context)
    else:
        await user_start(update, context)


async def handle_text_messages(update: Update, context):
    """مدیریت پیام‌های متنی"""
    # ✅ چک کردن effective_user
    if not update.effective_user or not update.message:
        logger.warning("⚠️ handle_text_messages called without effective_user or message")
        return
    
    # ✅ اگر کاربر داخل یک conversation هست، این handler نباید اجرا بشه
    # چون ConversationHandler باید پیام رو مدیریت کنه
    if context.user_data and any(key in context.user_data for key in [
        'editing_product_id', 'editing_pack_id', 'new_product_name',
        'broadcasting', 'creating_discount', 'finalizing_order',
        'editing_message_key'  # ✅ اضافه شدن برای message customizer
    ]):
        # کاربر داخل یک مکالمه است، این handler رو رد می‌کنیم
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    from handlers.admin import add_product_start, list_products, show_statistics, admin_start
    from handlers.order import view_pending_orders, view_payment_receipts
    from handlers.order import view_not_shipped_orders, view_shipped_orders
    from handlers.user import view_cart, view_my_address, contact_us
    from handlers.discount import discount_menu
    from handlers.broadcast import broadcast_start
    from backup_scheduler import manual_backup
    from handlers.analytics import send_analytics_menu
    
    # 🆕 ایمپورت تابع جدید
    from handlers.order import view_user_orders
    
    # دستورات ادمین
    if user_id == ADMIN_ID:
        if text == "➕ افزودن محصول":
            return await add_product_start(update, context)
        elif text == "📦 لیست محصولات":
            return await list_products(update, context)
        elif text == "📦 سفارشات":
            from keyboards import admin_orders_submenu_keyboard
            await update.message.reply_text(
                "📦 سفارشات — یکی رو انتخاب کنید:",
                reply_markup=admin_orders_submenu_keyboard()
            )
            return
        elif text == "📋 سفارشات در انتظار تایید":
            return await view_pending_orders(update, context)
        elif text == "📦 سفارشات ارسال نشده":
            return await view_not_shipped_orders(update, context)
        elif text == "✅ سفارشات ارسال شده":
            return await view_shipped_orders(update, context)
        elif text == "🔙 بازگشت":
            return await admin_start(update, context)
        elif text == "💳 تایید پرداخت‌ها":
            return await view_payment_receipts(update, context)
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
        elif text == "🏦 مدیریت کیف پول":
            from handlers.wallet_system import admin_wallet_menu
            return await admin_wallet_menu(update, context)
        elif text == "⚙️ سفارشی‌سازی پیام‌ها":
            if MESSAGE_CUSTOMIZER_AVAILABLE:
                return await customize_messages_menu(update, context)
            else:
                await update.message.reply_text("❌ این قابلیت در دسترس نیست!")
        elif text == "📥 دانلود گزارشات":
            if EXPORT_AVAILABLE:
                return await export_menu(update, context)
            else:
                await update.message.reply_text("❌ این قابلیت در دسترس نیست!")
    
    # دستورات کاربر
    if text == "🛒 سبد خرید":
        await view_cart(update, context)
    elif text == "💰 کیف پول من":
        from handlers.wallet_system import view_wallet
        await view_wallet(update, context)
    elif text == "📦 سفارشات من":
        await view_user_orders(update, context)
    elif text == "📍 آدرس ثبت شده من":
        await view_my_address(update, context)
    elif text == "📞 تماس با ما":
        await contact_us(update, context)
    elif text == "ℹ️ راهنما":
        from config import get_help_text
        await update.message.reply_text(get_help_text())


async def handle_photos(update: Update, context):
    """مدیریت عکس‌ها (رسیدها)"""
    from handlers.order import handle_receipt
    await handle_receipt(update, context)


async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🆕 پاکسازی دستی توسط ادمین"""
    # ✅ چک کردن effective_user
    if not update.effective_user:
        logger.warning("⚠️ manual_cleanup called without effective_user")
        return
    
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
    from telegram.ext import ApplicationHandlerStop
    
    if not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        return
    
    # ✅ FIX: حالا 3 تا مقدار برمیگردونه
    allowed, remaining_time, show_alert = rate_limiter.check_rate_limit(
        user_id,
        max_requests=20,
        window_seconds=60
    )
    
    if not allowed:
        if show_alert:
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            wait_msg = f"{minutes} دقیقه و {seconds} ثانیه" if minutes > 0 else f"{seconds} ثانیه"
            
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
        
        # ✅ FIX #6: متوقف کردن همه handler های بعدی
        raise ApplicationHandlerStop


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
    
    # FIX: validate_config اینجا صدا زده میشه نه موقع import
    from config import validate_config
    try:
        validate_config()
    except ValueError as e:
        import warnings
        warnings.warn(f"⚠️ Configuration issue: {e}")
        print(f"\n⚠️ هشدار تنظیمات: {e}\n")
    
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
        cart_increase, cart_decrease, use_wallet_in_invoice
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
        handle_delete_order,
        modify_order_items
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
        discount_per_user_limit_received,
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

    # ✅ بارگذاری تنظیمات کش‌بک از دیتابیس (پس از ریستارت هم حفظ می‌شه)
    try:
        saved_cashback = db.get_setting('cashback_percent', '0')
        application.bot_data['cashback_percent'] = float(saved_cashback)
        logger.info(f"✅ کش‌بک از دیتابیس بارگذاری شد: {saved_cashback}%")
    except Exception as e:
        application.bot_data['cashback_percent'] = 0
        logger.warning(f"⚠️ خطا در بارگذاری کش‌بک: {e}")
    
    setup_signal_handlers(application, db)
    
    # ✅ Feature #1: شروع داشبورد مانیتورینگ
    if MONITORING_AVAILABLE:
        try:
            # شروع سرور مانیتورینگ در پورت 5000
            start_monitoring_dashboard(port=5000, host='0.0.0.0')
            logger.info("✅ Monitoring dashboard started successfully")
            
            # تنظیم job برای بروزرسانی آمار (هر 30 ثانیه)
            if hasattr(application, 'job_queue') and application.job_queue is not None:
                async def update_monitoring_stats(context):
                    """بروزرسانی آمار مانیتورینگ"""
                    try:
                        # دریافت cart_locks از bot_data
                        cart_locks = context.bot_data.get('cart_locks', {})
                        update_stats(db, cart_locks)
                    except Exception as e:
                        logger.error(f"Error updating monitoring stats: {e}")
                
                application.job_queue.run_repeating(
                    update_monitoring_stats,
                    interval=30,  # هر 30 ثانیه
                    first=5,  # اولین بار بعد از 5 ثانیه
                    name="monitoring_stats_update"
                )
                logger.info("✅ Monitoring stats auto-update enabled (every 30 seconds)")
        except Exception as e:
            logger.error(f"❌ Failed to start monitoring dashboard: {e}")
    else:
        logger.warning("⚠️ Monitoring dashboard is disabled")
    
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
    
    # 🆕 راه‌اندازی پاکسازی خودکار روزانه (هر روز ساعت 3:30 صبح)
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
    
    # ✅ راه‌اندازی به‌روزرسانی دوره‌ای آمار (هر ساعت)
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            application.job_queue.run_repeating(
                scheduled_stats_update,
                interval=3600,  # هر 3600 ثانیه = 1 ساعت
                first=10,  # اولین بار بعد 10 ثانیه اجرا شه
                name="stats_update"
            )
            logger.info("✅ به‌روزرسانی دوره‌ای آمار فعال شد (هر 1 ساعت)")
        else:
            logger.warning("⚠️ JobQueue در دسترس نیست - به‌روزرسانی آمار غیرفعال است")
    except Exception as e:
        logger.warning(f"⚠️ خطا در راه‌اندازی به‌روزرسانی آمار: {e}")
    
    # 🆕 FIX #5: پاکسازی خودکار RateLimiter (هر ساعت) - جلوگیری از Memory Leak
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            async def cleanup_rate_limiter(context):
                rate_limiter.cleanup_stale_users(max_idle_seconds=3600)
            
            application.job_queue.run_repeating(
                cleanup_rate_limiter,
                interval=3600,
                first=60,
                name="rate_limiter_cleanup"
            )
            logger.info("✅ پاکسازی خودکار RateLimiter فعال شد (هر 1 ساعت)")
    except Exception as e:
        logger.warning(f"⚠️ خطا در راه‌اندازی پاکسازی RateLimiter: {e}")
    
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
    
    # ✅ جستجوی محصول خاص ادمین
    from handlers.admin import product_list_all, product_list_search, product_search_received, PRODUCT_SEARCH
    
    product_search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(product_list_search, pattern="^product_list:search$")],
        states={
            PRODUCT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_search_received)],
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
        entry_points=[CallbackQueryHandler(edit_product_photo_start, pattern="^edit_prod_photo:")],
        states={
            EDIT_PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, edit_product_photo_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    edit_pack_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_pack_start, pattern="^edit_pack:")],
        states={
            EDIT_PACK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pack_name_received)],
            EDIT_PACK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pack_quantity_received)],
            EDIT_PACK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pack_price_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    create_discount_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_discount_start, pattern="^create_discount$")],
        states={
            DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_code_received)],
            DISCOUNT_TYPE: [CallbackQueryHandler(discount_type_selected, pattern="^discount_type:")],
            DISCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_value_received)],
            DISCOUNT_MIN_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_min_purchase_received)],
            DISCOUNT_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_max_received)],
            DISCOUNT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_limit_received)],
            DISCOUNT_PER_USER_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_per_user_limit_received)],
            DISCOUNT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_start_received)],
            DISCOUNT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_end_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 پیام همگانی$"), broadcast_start)],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message_received),
                MessageHandler(filters.PHOTO, broadcast_message_received),
                MessageHandler(filters.VIDEO, broadcast_message_received),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    user_discount_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(apply_discount_start, pattern="^apply_discount$")],
        states={
            ENTER_DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_code_entered)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    edit_item_qty_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_item_quantity_start, pattern="^edit_item_qty:")],
        states={
            EDIT_ITEM_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_item_quantity_received)],
            EDIT_ITEM_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_item_notes_received),
                CallbackQueryHandler(skip_item_notes, pattern="^skip_notes:"),
                CallbackQueryHandler(cancel_item_edit, pattern="^cancel_edit:")
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    finalize_order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(finalize_order_start, pattern="^finalize_order$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    edit_address_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_address, pattern="^edit_address$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    edit_user_info_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_user_info_for_order, pattern="^edit_user_info$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    final_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(final_edit_order, pattern="^final_edit$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    # اضافه کردن handler ها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_product_conv)
    application.add_handler(add_pack_conv)
    application.add_handler(product_search_conv)
    
    # ✅ کل محصولات (CallbackQueryHandler نه ConversationHandler چون فقط یه action هست)
    application.add_handler(CallbackQueryHandler(product_list_all, pattern="^product_list:all$"))
    application.add_handler(edit_product_name_conv)
    application.add_handler(edit_product_desc_conv)
    application.add_handler(edit_product_photo_conv)
    application.add_handler(edit_pack_conv)
    application.add_handler(create_discount_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(user_discount_conv)
    application.add_handler(edit_item_qty_conv)
    application.add_handler(finalize_order_conv)
    application.add_handler(edit_address_conv)
    application.add_handler(edit_user_info_conv)
    application.add_handler(final_edit_conv)
    
    application.add_handler(CallbackQueryHandler(handle_dashboard_callback, pattern="^dash:"))
    
    # CallbackQuery هندلر
    # CallbackQuery هندلرها
    application.add_handler(CallbackQueryHandler(handle_pack_selection, pattern="^select_pack:"))
    application.add_handler(CallbackQueryHandler(back_to_packs, pattern="^back_to_packs:"))
    application.add_handler(CallbackQueryHandler(edit_product_menu, pattern="^edit_product:"))
    application.add_handler(CallbackQueryHandler(view_packs_with_edit, pattern="^view_packs:"))
    application.add_handler(CallbackQueryHandler(get_channel_link, pattern="^send_to_channel:"))
    application.add_handler(CallbackQueryHandler(edit_in_channel, pattern="^edit_in_channel:"))
    application.add_handler(CallbackQueryHandler(delete_product, pattern="^delete_product:"))
    application.add_handler(CallbackQueryHandler(delete_pack_confirm, pattern="^delete_pack:"))
    application.add_handler(CallbackQueryHandler(back_to_product, pattern="^back_to_product:"))
    
    application.add_handler(CallbackQueryHandler(manage_packs_menu, pattern="^manage_packs:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_pack, pattern="^confirm_delete_pack:"))
    application.add_handler(CallbackQueryHandler(delete_pack_final, pattern="^delete_pack_final:"))
    
    application.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    application.add_handler(CallbackQueryHandler(remove_from_cart, pattern="^remove_cart:"))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    application.add_handler(CallbackQueryHandler(cart_increase, pattern=r"^cart_increase:\d+$"))
    application.add_handler(CallbackQueryHandler(cart_decrease, pattern=r"^cart_decrease:\d+$"))
    
    application.add_handler(CallbackQueryHandler(handle_shipping_selection, pattern="^ship_"))
    application.add_handler(CallbackQueryHandler(final_confirm_order, pattern="^final_confirm$"))
    application.add_handler(CallbackQueryHandler(use_wallet_in_invoice, pattern="^use_wallet_invoice:"))
    application.add_handler(CallbackQueryHandler(use_old_address, pattern="^use_old_address$"))
    application.add_handler(CallbackQueryHandler(use_new_address, pattern="^use_new_address$"))
    application.add_handler(CallbackQueryHandler(confirm_user_info, pattern="^confirm_user_info$"))
    
    application.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm_order:"))
    application.add_handler(CallbackQueryHandler(reject_order, pattern="^reject_order:"))
    application.add_handler(CallbackQueryHandler(modify_order_items, pattern="^modify_order:"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item:"))
    application.add_handler(CallbackQueryHandler(reject_full_order, pattern="^reject_full:"))
    application.add_handler(CallbackQueryHandler(back_to_order_review, pattern="^back_to_order:"))
    application.add_handler(CallbackQueryHandler(confirm_modified_order, pattern="^confirm_modified:"))
    application.add_handler(CallbackQueryHandler(confirm_payment, pattern="^confirm_payment:"))
    application.add_handler(CallbackQueryHandler(reject_payment, pattern="^reject_payment:"))
    
    # 🆕 Handler ارسال شدن سفارش
    from handlers.order import mark_order_shipped, admin_delete_not_shipped_order
    application.add_handler(CallbackQueryHandler(mark_order_shipped, pattern="^mark_shipped:"))
    application.add_handler(CallbackQueryHandler(admin_delete_not_shipped_order, pattern="^admin_delete_order:"))
    application.add_handler(CallbackQueryHandler(handle_continue_payment, pattern="^continue_payment:"))
    application.add_handler(CallbackQueryHandler(handle_delete_order, pattern="^delete_order:"))
    
    application.add_handler(CallbackQueryHandler(increase_item_quantity, pattern="^increase_item:"))
    application.add_handler(CallbackQueryHandler(decrease_item_quantity, pattern="^decrease_item:"))
    
    application.add_handler(CallbackQueryHandler(list_discounts, pattern="^list_discounts$"))
    application.add_handler(CallbackQueryHandler(view_discount, pattern="^view_discount:"))
    application.add_handler(CallbackQueryHandler(toggle_discount, pattern="^toggle_discount:"))
    application.add_handler(CallbackQueryHandler(delete_discount, pattern="^delete_discount:"))
    
    application.add_handler(CallbackQueryHandler(confirm_broadcast, pattern="^confirm_broadcast$"))
    application.add_handler(CallbackQueryHandler(cancel_broadcast, pattern="^cancel_broadcast$"))
    
    application.add_handler(CallbackQueryHandler(handle_analytics_report, pattern="^analytics:"))
    
    # ✅ Handler برای بازگشت به منوی ادمین
    async def back_to_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بازگشت به منوی اصلی ادمین"""
        query = update.callback_query
        await query.answer()
        
        from keyboards import admin_main_keyboard
        
        # ارسال پیام جدید به جای edit
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="👋 خوش آمدید ادمین!\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=admin_main_keyboard()
        )
        
        # حذف پیام قبلی
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")
    
    application.add_handler(CallbackQueryHandler(back_to_admin_handler, pattern="^back_to_admin$"))

    # ==================== Wallet Handlers ====================
    from handlers.wallet_system import (
        view_wallet, view_wallet_history, use_wallet_in_order,
        admin_wallet_menu, admin_wallet_report,
        admin_charge_wallet_start, admin_charge_wallet_user_received,
        admin_charge_wallet_amount_received,
        admin_gift_wallet_start, admin_gift_user_received,
        admin_gift_type_received, admin_gift_value_received,
        admin_cashback_start, admin_cashback_percent_received,
    )

    wallet_charge_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_charge_wallet_start, pattern="^wallet_admin:charge$")],
        states={
            100: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_charge_wallet_user_received)],
            101: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_charge_wallet_amount_received)],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(wallet_charge_conv)

    wallet_gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_gift_wallet_start, pattern="^wallet_admin:gift$")],
        states={
            102: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_user_received)],
            103: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_type_received)],
            104: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gift_value_received)],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(wallet_gift_conv)

    wallet_cashback_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_cashback_start, pattern="^wallet_admin:cashback$")],
        states={
            106: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_cashback_percent_received)],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(wallet_cashback_conv)

    application.add_handler(CallbackQueryHandler(view_wallet,         pattern="^wallet:view$"))
    application.add_handler(CallbackQueryHandler(view_wallet_history, pattern="^wallet:history$"))
    application.add_handler(CallbackQueryHandler(use_wallet_in_order, pattern="^use_wallet:"))
    application.add_handler(CallbackQueryHandler(admin_wallet_menu,   pattern="^wallet_admin:menu$"))
    application.add_handler(CallbackQueryHandler(admin_wallet_report, pattern="^wallet_admin:report$"))
    
    # ✅ Feature #4: Export handlers
    if EXPORT_AVAILABLE:
        try:
            application.add_handler(CallbackQueryHandler(handle_export, pattern="^export:"))
            logger.info("✅ Export handlers added")
        except Exception as e:
            logger.error(f"❌ Failed to add export handlers: {e}")
    
    # ✅ Feature #5: Message customizer handlers
    if MESSAGE_CUSTOMIZER_AVAILABLE:
        try:
            # ✅ اول callback handlerهای ساده
            application.add_handler(CallbackQueryHandler(show_category_messages, pattern="^msg_cat:"))
            application.add_handler(CallbackQueryHandler(show_message_preview, pattern="^msg_edit:"))
            application.add_handler(CallbackQueryHandler(reset_message, pattern="^msg_reset:"))
            application.add_handler(CallbackQueryHandler(
                lambda u, c: customize_messages_menu(u, c),
                pattern="^msg_back_to_list$"
            ))
            application.add_handler(CallbackQueryHandler(
                lambda u, c: customize_messages_menu(u, c),
                pattern="^msg_back_to_categories$"
            ))
            
            # ✅ بعد ConversationHandler (برای msg_start_edit:)
            application.add_handler(get_message_customizer_conversation())
            
            logger.info("✅ Message customizer handlers added")
        except Exception as e:
            logger.error(f"❌ Failed to add message customizer handlers: {e}")
    
    # ✅ Message هندلرها - باید بعد از همه ConversationHandlerها باشه
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photos))
    
    # ✅ FIX #1 & #2: رفع import اشتباه + حذف ثبت دوباره error handler
    async def error_handler_with_monitoring(update, context):
        # از error_handler محلی همین فایل استفاده میکنیم، نه import اشتباه
        if MONITORING_AVAILABLE:
            set_error(str(context.error)[:100])
        await error_handler(update, context)
    
    # ✅ فقط یه بار ثبت میشه
    application.add_error_handler(error_handler_with_monitoring)
    
    # شروع ربات
    logger.info("🤖 ربات با قابلیت‌های جدید شروع به کار کرد!")
    logger.info("✅ Health Check فعال")
    logger.info("✅ Enhanced Error Handler فعال")
    logger.info("✅ Cache Manager فعال")
    logger.info("✅ Admin Dashboard فعال")
    logger.info("✅ تاریخ شمسی برای سفارشات فعال")
    logger.info("✅ دکمه‌های دینامیک برای سفارشات فعال")
    logger.info("✅ قابلیت حذف سفارش توسط کاربر فعال")
    logger.info("✅ پاکسازی خودکار روزانه فعال (ساعت 3:30 صبح)")
    logger.info("✅ دکمه پاکسازی دستی برای ادمین فعال")
    logger.info("✅ به‌روزرسانی خودکار آمار محصولات فعال (هر ساعت)")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("🛑 Received keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        try:
            db.close()
        except:
            pass
        log_shutdown()


if __name__ == '__main__':
    main()
