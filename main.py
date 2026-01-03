"""
ربات فروشگاه مانتو تلگرام
فایل اصلی - نسخه کامل با قابلیت‌های جدید
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    JobQueue
)

# ایمپورت ماژول‌های پروژه
from config import BOT_TOKEN, ADMIN_ID
from database import Database
from states import *

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
    from handlers.order import view_pending_orders, view_payment_receipts
    from handlers.user import view_cart, view_my_orders, view_my_address, contact_us
    from handlers.discount import discount_menu
    from handlers.broadcast import broadcast_start
    from backup_scheduler import manual_backup
    from handlers.analytics import send_analytics_menu  # موقتاً غیرفعال
    
    # دستورات ادمین
    if user_id == ADMIN_ID:
        if text == "➕ افزودن محصول":
            return await add_product_start(update, context)
        elif text == "📦 لیست محصولات":
            return await list_products(update, context)
        elif text == "📋 سفارشات جدید":
            return await view_pending_orders(update, context)
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
    
    # دستورات کاربر
    if text == "🛒 سبد خرید":
        await view_cart(update, context)
    elif text == "📦 سفارشات من":
        await view_my_orders(update, context)
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
            "5️⃣ سفارش خود را نهایی کنید\n"
            "6️⃣ بعد از تایید، مبلغ را واریز کنید\n"
            "7️⃣ رسید را ارسال کنید\n"
            "8️⃣ سفارش شما ارسال می‌شود! 🎉"
        )


async def handle_photos(update: Update, context):
    """مدیریت عکس‌ها (رسیدها)"""
    from handlers.order import handle_receipt
    await handle_receipt(update, context)


async def error_handler(update: Update, context):
    """مدیریت خطاها"""
    logger.error(f"خطا: {context.error}")


def main():
    """تابع اصلی"""
    # Import توابع admin
    from handlers.admin import (
        add_product_start, product_name_received, product_desc_received,
        product_photo_received, add_pack_start, pack_name_received,
        pack_quantity_received, pack_price_received,
        get_channel_link, delete_product, admin_start
    )
    
    # Import توابع admin_extended (ویرایش)
    from handlers.admin_extended import (
        edit_product_menu, edit_product_name_start, edit_product_name_received,
        edit_product_desc_start, edit_product_desc_received,
        edit_product_photo_start, edit_product_photo_received,
        view_packs_with_edit, edit_pack_start, edit_pack_name_received,
        edit_pack_quantity_received, edit_pack_price_received,
        delete_pack_confirm, edit_in_channel, back_to_product
    )
    
    # 🆕 Import توابع admin_pack_management (مدیریت پک‌ها)
    from handlers.admin_pack_management import (
        manage_packs_menu,
        confirm_delete_pack,
        delete_pack_final
    )
    
    # Import توابع user
    from handlers.user import (
        finalize_order_start, full_name_received, address_text_received, 
        phone_number_received, use_old_address,
        use_new_address, handle_pack_selection, view_cart,
        remove_from_cart, clear_cart, handle_shipping_selection,
        final_confirm_order, final_edit_order, edit_address,
        back_to_packs, user_start, confirm_user_info, edit_user_info_for_order
    )
    
    # Import توابع order
    from handlers.order import (
        confirm_order, reject_order, confirm_payment, reject_payment,
        remove_item_from_order, reject_full_order, back_to_order_review,
        confirm_modified_order
    )
    
    # Import توابع discount
    from handlers.discount import (
        create_discount_start, discount_code_received, discount_type_selected,
        discount_value_received, discount_min_purchase_received,
        discount_max_received, discount_limit_received,
        discount_start_received, discount_end_received,
        list_discounts, view_discount, toggle_discount, delete_discount
    )
    
    # Import توابع broadcast
    from handlers.broadcast import (
        broadcast_message_received, confirm_broadcast, cancel_broadcast
    )
    
    # Import توابع analytics
    from handlers.analytics import handle_analytics_report
    
    # ایجاد دیتابیس
    db = Database()
    
    # ساخت اپلیکیشن با فعال‌سازی Job Queue
    try:
        # روش 1: استفاده از job_queue در builder
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .job_queue(JobQueue())
            .build()
        )
        logger.info("✅ Application با JobQueue ساخته شد")
    except Exception as e:
        logger.warning(f"⚠️ خطا در ساخت JobQueue: {e}")
        # اگر روش اول کار نکرد، به روش معمولی بساز
        application = Application.builder().token(BOT_TOKEN).build()
    
    # ذخیره دیتابیس در bot_data
    application.bot_data['db'] = db
    
    # راه‌اندازی بکاپ خودکار
    from backup_scheduler import setup_backup_job, setup_backup_folder
    setup_backup_folder()
    
    # تلاش برای فعال‌سازی بکاپ خودکار
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            setup_backup_job(application)
            logger.info("✅ بکاپ خودکار روزانه فعال شد")
        else:
            logger.warning("⚠️ JobQueue در دسترس نیست - بکاپ خودکار غیرفعال است")
            logger.warning("💡 بکاپ دستی از طریق دکمه '💾 بکاپ دستی' قابل استفاده است")
    except Exception as e:
        logger.warning(f"⚠️ خطا در راه‌اندازی بکاپ خودکار: {e}")
        logger.warning("💡 بکاپ دستی از طریق دکمه '💾 بکاپ دستی' قابل استفاده است")
    
    # ==================== ConversationHandler برای افزودن محصول ====================
    add_product_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ افزودن محصول$"), add_product_start)],
        states={
            PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_name_received)],
            PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_desc_received)],
            PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, product_photo_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای افزودن پک ====================
    add_pack_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_pack_start, pattern="^add_pack:")],
        states={
            PACK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_name_received)],
            PACK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_quantity_received)],
            PACK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_price_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش نام محصول ====================
    edit_product_name_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_product_name_start, pattern="^edit_prod_name:")],
        states={
            EDIT_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_name_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش توضیحات محصول ====================
    edit_product_desc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_product_desc_start, pattern="^edit_prod_desc:")],
        states={
            EDIT_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_desc_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش عکس محصول ====================
    edit_product_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_product_photo_start, pattern="^edit_prod_photo:")],
        states={
            EDIT_PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, edit_product_photo_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش پک ====================
    edit_pack_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_pack_start, pattern="^edit_pack:")],
        states={
            EDIT_PACK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pack_name_received)],
            EDIT_PACK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pack_quantity_received)],
            EDIT_PACK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pack_price_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای ایجاد تخفیف ====================
    create_discount_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_discount_start, pattern="^create_discount$")],
        states={
            DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_code_received)],
            DISCOUNT_TYPE: [CallbackQueryHandler(discount_type_selected, pattern="^discount_type:")],
            DISCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_value_received)],
            DISCOUNT_MIN_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_min_purchase_received)],
            DISCOUNT_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_max_received)],
            DISCOUNT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_limit_received)],
            DISCOUNT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_start_received)],
            DISCOUNT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_end_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای پیام همگانی ====================
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 پیام همگانی$"), broadcast_message_received)],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message_received),
                MessageHandler(filters.PHOTO, broadcast_message_received),
                MessageHandler(filters.VIDEO, broadcast_message_received),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), admin_start)],
    )
    
    # ==================== ConversationHandler برای نهایی کردن سفارش ====================
    finalize_order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(finalize_order_start, pattern="^finalize_order$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش آدرس ====================
    edit_address_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_address, pattern="^edit_address$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش اطلاعات موقع سفارش ====================
    edit_user_info_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_user_info_for_order, pattern="^edit_user_info$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    # ==================== ConversationHandler برای ویرایش در فاکتور نهایی ====================
    final_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(final_edit_order, pattern="^final_edit$")],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), user_start)],
    )
    
    # ==================== هندلرهای اصلی ====================
    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_product_conv)
    application.add_handler(add_pack_conv)
    application.add_handler(edit_product_name_conv)
    application.add_handler(edit_product_desc_conv)
    application.add_handler(edit_product_photo_conv)
    application.add_handler(edit_pack_conv)
    application.add_handler(create_discount_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(finalize_order_conv)
    application.add_handler(edit_address_conv)
    application.add_handler(edit_user_info_conv)
    application.add_handler(final_edit_conv)
    
    # ==================== CallbackQuery هندلرها ====================
    # محصولات و پک‌ها
    application.add_handler(CallbackQueryHandler(handle_pack_selection, pattern="^select_pack:"))
    application.add_handler(CallbackQueryHandler(back_to_packs, pattern="^back_to_packs:"))
    application.add_handler(CallbackQueryHandler(edit_product_menu, pattern="^edit_product:"))
    application.add_handler(CallbackQueryHandler(view_packs_with_edit, pattern="^view_packs:"))
    application.add_handler(CallbackQueryHandler(get_channel_link, pattern="^send_to_channel:"))
    application.add_handler(CallbackQueryHandler(edit_in_channel, pattern="^edit_in_channel:"))
    application.add_handler(CallbackQueryHandler(delete_product, pattern="^delete_product:"))
    application.add_handler(CallbackQueryHandler(delete_pack_confirm, pattern="^delete_pack:"))
    application.add_handler(CallbackQueryHandler(back_to_product, pattern="^back_to_product:"))
    
    # 🆕 مدیریت پک‌ها (handler های جدید)
    application.add_handler(CallbackQueryHandler(manage_packs_menu, pattern="^manage_packs:"))
    application.add_handler(CallbackQueryHandler(confirm_delete_pack, pattern="^confirm_delete_pack:"))
    application.add_handler(CallbackQueryHandler(delete_pack_final, pattern="^delete_pack_final:"))
    
    # سبد خرید
    application.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    application.add_handler(CallbackQueryHandler(remove_from_cart, pattern="^remove_cart:"))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    
    # سفارش
    application.add_handler(CallbackQueryHandler(handle_shipping_selection, pattern="^ship_"))
    application.add_handler(CallbackQueryHandler(final_confirm_order, pattern="^final_confirm$"))
    application.add_handler(CallbackQueryHandler(use_old_address, pattern="^use_old_address$"))
    application.add_handler(CallbackQueryHandler(use_new_address, pattern="^use_new_address$"))
    application.add_handler(CallbackQueryHandler(confirm_user_info, pattern="^confirm_user_info$"))
    
    # هندلرهای سفارش (ادمین)
    application.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm_order:"))
    application.add_handler(CallbackQueryHandler(reject_order, pattern="^reject_order:"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item:"))
    application.add_handler(CallbackQueryHandler(reject_full_order, pattern="^reject_full:"))
    application.add_handler(CallbackQueryHandler(back_to_order_review, pattern="^back_to_order:"))
    application.add_handler(CallbackQueryHandler(confirm_modified_order, pattern="^confirm_modified:"))
    application.add_handler(CallbackQueryHandler(confirm_payment, pattern="^confirm_payment:"))
    application.add_handler(CallbackQueryHandler(reject_payment, pattern="^reject_payment:"))
    
    # تخفیف‌ها
    application.add_handler(CallbackQueryHandler(list_discounts, pattern="^list_discounts$"))
    application.add_handler(CallbackQueryHandler(view_discount, pattern="^view_discount:"))
    application.add_handler(CallbackQueryHandler(toggle_discount, pattern="^toggle_discount:"))
    application.add_handler(CallbackQueryHandler(delete_discount, pattern="^delete_discount:"))
    
    # پیام همگانی
    application.add_handler(CallbackQueryHandler(confirm_broadcast, pattern="^confirm_broadcast$"))
    application.add_handler(CallbackQueryHandler(cancel_broadcast, pattern="^cancel_broadcast$"))
    
    # گزارش‌های تحلیلی - موقتاً غیرفعال
     application.add_handler(CallbackQueryHandler(handle_analytics_report, pattern="^analytics:"))
    
    # ==================== Message هندلرها ====================
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photos))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # شروع ربات
    logger.info("🤖 ربات شروع به کار کرد!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
