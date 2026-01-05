"""
سیستم پیام‌رسانی همگانی
🔥 FIX: Batch Processing با Progress Bar
✅ Error handling بهتر
✅ Rate limiting هوشمند
✅ Retry mechanism
"""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from logger import log_broadcast, log_error
from states import BROADCAST_MESSAGE
from keyboards import cancel_keyboard, admin_main_keyboard, broadcast_confirm_keyboard
from telegram.error import TelegramError, Forbidden, BadRequest


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع پیام همگانی"""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    # پاک کردن پیام قبلی
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
    """
    🔥 FIX: تایید و ارسال پیام همگانی با Batch Processing
    """
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    
    try:
        users = db.get_all_users()
    except Exception as e:
        log_error("Broadcast", f"خطا در دریافت لیست کاربران: {e}")
        await query.edit_message_text(
            "❌ خطا در دریافت لیست کاربران!",
            reply_markup=admin_main_keyboard()
        )
        return
    
    broadcast_type = context.user_data.get('broadcast_type')
    broadcast_content = context.user_data.get('broadcast_content')
    broadcast_caption = context.user_data.get('broadcast_caption', '')
    
    if not broadcast_type or not broadcast_content:
        await query.edit_message_text("❌ خطا! پیامی یافت نشد.")
        return
    
    # ایجاد پیام Progress
    progress_message = await query.edit_message_text(
        f"⏳ **در حال ارسال...**\n\n"
        f"📊 پیشرفت: 0/{len(users)} (0%)\n"
        f"✅ موفق: 0\n"
        f"❌ خطا: 0\n"
        f"🚫 بلاک: 0"
    )
    
    # 🔥 Batch Processing با Progress Bar
    success_count = 0
    failed_count = 0
    blocked_count = 0
    
    BATCH_SIZE = 20  # ارسال 20 تا 20 تا
    DELAY_BETWEEN_BATCHES = 1  # 1 ثانیه تاخیر بین batch ها
    DELAY_PER_MESSAGE = 0.05  # 50ms تاخیر بین هر پیام
    
    total = len(users)
    
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = users[batch_start:batch_end]
        
        # ارسال batch فعلی
        tasks = []
        for user in batch:
            user_id = user[0]
            tasks.append(send_broadcast_message(
                context, user_id, broadcast_type, 
                broadcast_content, broadcast_caption
            ))
        
        # اجرای همزمان با gather
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # پردازش نتایج
        for result in results:
            if isinstance(result, Exception):
                error_msg = str(result).lower()
                if any(x in error_msg for x in ["blocked", "deactivated", "not found"]):
                    blocked_count += 1
                else:
                    failed_count += 1
            elif result is True:
                success_count += 1
            else:
                failed_count += 1
        
        # 🔥 بروزرسانی Progress Bar
        current = batch_end
        percent = int((current / total) * 100)
        
        # محاسبه نوار پیشرفت
        filled = int(percent / 5)  # هر 5% = یک بلوک
        bar = "█" * filled + "░" * (20 - filled)
        
        try:
            await progress_message.edit_text(
                f"⏳ **در حال ارسال...**\n\n"
                f"📊 پیشرفت: {current}/{total} ({percent}%)\n"
                f"{bar}\n\n"
                f"✅ موفق: {success_count}\n"
                f"❌ خطا: {failed_count}\n"
                f"🚫 بلاک: {blocked_count}\n\n"
                f"⏱ لطفاً صبر کنید..."
            )
        except:
            pass  # اگه خطای "message not modified" داد
        
        # تاخیر بین batch ها
        if batch_end < total:
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)
    
    # لاگ broadcast
    log_broadcast(
        update.effective_user.id,
        success_count,
        failed_count + blocked_count,
        len(users)
    )
    
    # گزارش نهایی
    success_rate = (success_count / len(users) * 100) if len(users) > 0 else 0
    
    final_bar = "█" * 20
    
    report = "✅ **ارسال پیام همگانی تکمیل شد!**\n\n"
    report += f"{final_bar}\n\n"
    report += f"📊 **نتایج:**\n"
    report += f"├ ✅ موفق: {success_count}\n"
    report += f"├ 🚫 بلاک شده: {blocked_count}\n"
    report += f"├ ❌ خطا: {failed_count}\n"
    report += f"└ 📈 نرخ موفقیت: {success_rate:.1f}%\n\n"
    report += f"📅 {total} کاربر هدف قرار گرفتند"
    
    await progress_message.edit_text(
        report,
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )
    
    # پاک کردن داده‌های موقت
    context.user_data.clear()


async def send_broadcast_message(context, user_id, msg_type, content, caption):
    """
    🔥 FIX: ارسال یک پیام broadcast با retry
    """
    MAX_RETRIES = 2
    
    for attempt in range(MAX_RETRIES):
        try:
            if msg_type == 'text':
                await context.bot.send_message(
                    user_id,
                    content,
                    parse_mode='Markdown'
                )
            elif msg_type == 'photo':
                await context.bot.send_photo(
                    user_id,
                    content,
                    caption=caption if caption else None,
                    parse_mode='Markdown' if caption else None
                )
            elif msg_type == 'video':
                await context.bot.send_video(
                    user_id,
                    content,
                    caption=caption if caption else None,
                    parse_mode='Markdown' if caption else None
                )
            
            return True
            
        except (Forbidden, BadRequest) as e:
            # خطاهای غیرقابل retry
            raise e
            
        except TelegramError as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)  # تاخیر قبل retry
            else:
                raise e
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
            else:
                raise e
    
    return False


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ارسال پیام همگانی"""
    query = update.callback_query
    await query.answer("لغو شد")
    
    await query.edit_message_text("❌ ارسال پیام همگانی لغو شد.")
    
    context.user_data.clear()
