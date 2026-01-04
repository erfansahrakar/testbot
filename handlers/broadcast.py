"""
سیستم پیام‌رسانی همگانی
🆕 اصلاح شده: حالا درست کار می‌کنه!
✅ FIX: ترتیب صحیح log_broadcast
"""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from logger import log_broadcast
from states import BROADCAST_MESSAGE
from keyboards import cancel_keyboard, admin_main_keyboard, broadcast_confirm_keyboard


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع پیام همگانی"""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    # 🆕 پاک کردن پیام قبلی اگه وجود داشته باشه
    context.user_data.pop('broadcast_type', None)
    context.user_data.pop('broadcast_content', None)
    context.user_data.pop('broadcast_caption', None)
    
    await update.message.reply_text(
        "📢 **پیام‌رسانی همگانی**\n\n"
        "پیام خود را برای ارسال به همه کاربران وارد کنید:\n\n"
        "✅ می‌توانید متن بفرستید\n"
        "✅ می‌توانید عکس + توضیحات بفرستید\n"
        "✅ می‌توانید ویدیو + توضیحات بفرستید\n\n"
        "⚠️ از فرمت Markdown هم می‌توانید استفاده کنید.",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return BROADCAST_MESSAGE


async def broadcast_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پیام برای ارسال"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    # ذخیره پیام
    if update.message.text:
        context.user_data['broadcast_type'] = 'text'
        context.user_data['broadcast_content'] = update.message.text
        preview = update.message.text[:100] + "..." if len(update.message.text) > 100 else update.message.text
    elif update.message.photo:
        context.user_data['broadcast_type'] = 'photo'
        context.user_data['broadcast_content'] = update.message.photo[-1].file_id
        context.user_data['broadcast_caption'] = update.message.caption if update.message.caption else ""
        preview = f"📷 عکس" + (f"\n{update.message.caption[:50]}..." if update.message.caption else "")
    elif update.message.video:
        context.user_data['broadcast_type'] = 'video'
        context.user_data['broadcast_content'] = update.message.video.file_id
        context.user_data['broadcast_caption'] = update.message.caption if update.message.caption else ""
        preview = f"🎥 ویدیو" + (f"\n{update.message.caption[:50]}..." if update.message.caption else "")
    else:
        await update.message.reply_text(
            "❌ فقط متن، عکس یا ویدیو پشتیبانی می‌شود!\n"
            "لطفاً دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return BROADCAST_MESSAGE
    
    # تعداد کاربران
    db = context.bot_data['db']
    users = db.get_all_users()
    user_count = len(users)
    
    await update.message.reply_text(
        f"📊 **پیش‌نمایش پیام:**\n\n"
        f"{preview}\n\n"
        f"👥 تعداد گیرندگان: {user_count} نفر\n\n"
        f"❓ آیا مطمئن هستید؟",
        parse_mode='Markdown',
        reply_markup=broadcast_confirm_keyboard()
    )
    
    return ConversationHandler.END


async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید و ارسال پیام همگانی"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    users = db.get_all_users()
    
    broadcast_type = context.user_data.get('broadcast_type')
    broadcast_content = context.user_data.get('broadcast_content')
    broadcast_caption = context.user_data.get('broadcast_caption', '')
    
    if not broadcast_type or not broadcast_content:
        await query.edit_message_text("❌ خطا! پیامی یافت نشد.")
        return
    
    await query.edit_message_text(
        f"⏳ در حال ارسال به {len(users)} کاربر...\n"
        f"لطفاً صبر کنید..."
    )
    
    # ✅ FIX: اول متغیرها رو تعریف کن
    success_count = 0
    failed_count = 0
    blocked_count = 0
    
    for user in users:
        user_id = user[0]
        
        try:
            if broadcast_type == 'text':
                await context.bot.send_message(
                    user_id,
                    broadcast_content,
                    parse_mode='Markdown'
                )
            elif broadcast_type == 'photo':
                await context.bot.send_photo(
                    user_id,
                    broadcast_content,
                    caption=broadcast_caption if broadcast_caption else None,
                    parse_mode='Markdown' if broadcast_caption else None
                )
            elif broadcast_type == 'video':
                await context.bot.send_video(
                    user_id,
                    broadcast_content,
                    caption=broadcast_caption if broadcast_caption else None,
                    parse_mode='Markdown' if broadcast_caption else None
                )
            
            success_count += 1
            
        except Exception as e:
            error_msg = str(e).lower()
            if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
                blocked_count += 1
            else:
                failed_count += 1
        
        # تاخیر کوچک برای جلوگیری از محدودیت تلگرام
        await asyncio.sleep(0.05)
    
    # ✅ FIX: حالا log_broadcast بعد از تعریف متغیرها فراخوانی میشه
    log_broadcast(
        update.effective_user.id,
        success_count,
        failed_count,
        len(users)
    )
    
    # گزارش نهایی
    report = "✅ **ارسال پیام همگانی تکمیل شد!**\n\n"
    report += f"✅ موفق: {success_count}\n"
    report += f"🚫 بلاک شده/غیرفعال: {blocked_count}\n"
    report += f"❌ خطا: {failed_count}\n"
    report += f"📊 کل: {len(users)}"
    
    await query.message.reply_text(
        report,
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )
    
    # پاک کردن داده‌های موقت
    context.user_data.clear()


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ارسال پیام همگانی"""
    query = update.callback_query
    await query.answer("لغو شد")
    
    await query.edit_message_text("❌ ارسال پیام همگانی لغو شد.")
    
    context.user_data.clear()
