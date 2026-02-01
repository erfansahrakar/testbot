"""
سیستم پیام‌رسانی همگانی
✅ FIX: Batch Processing با Progress Bar
✅ FIX: Error handling بهتر
✅ FIX: Retry mechanism
✅ بهینه‌سازی سرعت ارسال
"""
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import RetryAfter, TimedOut, NetworkError, Forbidden
from config import ADMIN_ID
from logger import log_broadcast, log_error
from states import BROADCAST_MESSAGE
from keyboards import cancel_keyboard, admin_main_keyboard, broadcast_confirm_keyboard
import logging

logger = logging.getLogger(__name__)

# 🔥 تنظیمات Batch Processing
BATCH_SIZE = 30  # ارسال به 30 نفر همزمان
BATCH_DELAY = 1  # تاخیر 1 ثانیه بین هر batch
RETRY_ATTEMPTS = 3  # تعداد تلاش مجدد


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع پیام همگانی"""
    # ✅ چک کردن effective_user
    if not update.effective_user:
        logger.warning("⚠️ broadcast_start called without effective_user")
        return ConversationHandler.END
    
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


async def send_message_to_user(context, user_id, broadcast_type, broadcast_content, broadcast_caption):
    """
    🔥 ارسال پیام به یک کاربر با Retry
    """
    for attempt in range(RETRY_ATTEMPTS):
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
            
            return 'success', None
        
        except Forbidden as e:
            # کاربر ربات را بلاک کرده
            return 'blocked', str(e)
        
        except RetryAfter as e:
            # محدودیت Telegram - صبر کن
            logger.warning(f"⚠️ RetryAfter {e.retry_after}s for user {user_id}")
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(e.retry_after)
            else:
                return 'rate_limited', str(e)
        
        except (TimedOut, NetworkError) as e:
            # مشکل شبکه - retry
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(2 ** attempt)  # exponential backoff
            else:
                return 'network_error', str(e)
        
        except Exception as e:
            # خطای دیگر
            logger.error(f"❌ Error sending to {user_id}: {e}")
            return 'error', str(e)
    
    return 'error', 'Max retries exceeded'


async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🔥 تایید و ارسال پیام همگانی با Batch Processing
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
    
    total_users = len(users)
    
    # پیام اولیه
    progress_msg = await query.edit_message_text(
        f"⏳ **در حال ارسال...**\n\n"
        f"👥 کل: {total_users} کاربر\n"
        f"📊 پیشرفت: 0%\n"
        f"✅ موفق: 0\n"
        f"❌ ناموفق: 0",
        parse_mode='Markdown'
    )
    
    # 🔥 شمارنده‌ها
    success_count = 0
    blocked_count = 0
    failed_count = 0
    rate_limited_count = 0
    
    # 🔥 Batch Processing
    for i in range(0, total_users, BATCH_SIZE):
        batch = users[i:i + BATCH_SIZE]
        batch_tasks = []
        
        # ایجاد task های همزمان برای این batch
        for user in batch:
            user_id = user[0]
            task = send_message_to_user(
                context, 
                user_id, 
                broadcast_type, 
                broadcast_content, 
                broadcast_caption
            )
            batch_tasks.append(task)
        
        # اجرای همزمان
        results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # پردازش نتایج
        for result in results:
            if isinstance(result, tuple):
                status, error = result
                if status == 'success':
                    success_count += 1
                elif status == 'blocked':
                    blocked_count += 1
                elif status == 'rate_limited':
                    rate_limited_count += 1
                else:
                    failed_count += 1
            else:
                # Exception رخ داده
                failed_count += 1
        
        # 🔥 به‌روزرسانی Progress
        processed = min(i + BATCH_SIZE, total_users)
        progress = int((processed / total_users) * 100)
        
        try:
            await progress_msg.edit_text(
                f"⏳ **در حال ارسال...**\n\n"
                f"👥 کل: {total_users} کاربر\n"
                f"📊 پیشرفت: {progress}% ({processed}/{total_users})\n\n"
                f"✅ موفق: {success_count}\n"
                f"🚫 بلاک: {blocked_count}\n"
                f"⚠️ Rate Limited: {rate_limited_count}\n"
                f"❌ خطا: {failed_count}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to update progress: {e}")
        
        # تاخیر بین batch ها
        if i + BATCH_SIZE < total_users:
            await asyncio.sleep(BATCH_DELAY)
    
    # لاگ broadcast
    log_broadcast(
        update.effective_user.id,
        success_count,
        blocked_count + failed_count + rate_limited_count,
        total_users
    )
    
    # 🔥 گزارش نهایی
    success_rate = (success_count / total_users * 100) if total_users > 0 else 0
    
    report = "✅ **ارسال پیام همگانی تکمیل شد!**\n\n"
    report += f"📊 **نتیجه:**\n"
    report += f"├ کل: {total_users}\n"
    report += f"├ ✅ موفق: {success_count}\n"
    report += f"├ 🚫 بلاک شده: {blocked_count}\n"
    report += f"├ ⚠️ محدودیت: {rate_limited_count}\n"
    report += f"└ ❌ خطا: {failed_count}\n\n"
    report += f"📈 **نرخ موفقیت:** {success_rate:.1f}%\n\n"
    
    if rate_limited_count > 0:
        report += f"⚠️ {rate_limited_count} کاربر به دلیل محدودیت Telegram پیام دریافت نکردند.\n"
    
    await progress_msg.edit_text(
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
