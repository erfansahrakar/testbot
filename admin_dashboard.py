"""
پنل مدیریتی پیشرفته

"""
import json
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
from logger import log_admin_action


def escape_markdown(text: str) -> str:
    """
    Escape کردن کاراکترهای ویژه Markdown
    برای جلوگیری از BadRequest: Can't parse entities
    """
    if not text:
        return ""
    
    # کاراکترهای ویژه که باید escape شوند
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    
    # Escape کردن
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))


async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش داشبورد اصلی ادمین"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    db = context.bot_data['db']
    
    # دریافت آمار
    stats = db.get_statistics()
    
    # Health Check
    health_checker = context.bot_data.get('health_checker')
    health_status = health_checker.get_health_status() if health_checker else None
    
    # Cache Stats
    cache_manager = context.bot_data.get('cache_manager')
    cache_stats = cache_manager.get_stats() if cache_manager else None
    
    # ساخت متن داشبورد
    text = "🎛 **داشبورد مدیریت**\n"
    text += "═" * 30 + "\n\n"
    
    # وضعیت سیستم
    if health_status:
        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'critical': '🔴'
        }
        emoji = status_emoji.get(health_status.status, '❓')
        text += f"**وضعیت سیستم:** {emoji} {health_status.status.upper()}\n\n"
    
    # آمار فروش
    text += "**📊 آمار فروش:**\n"
    text += f"├ کل سفارشات: {stats['total_orders']}\n"
    text += f"├ امروز: {stats['today_orders']}\n"
    text += f"├ در انتظار: {stats['pending_orders']}\n"
    text += f"└ درآمد کل: {stats['total_income']:,.0f} تومان\n\n"
    
    # آمار کاربران
    text += "**👥 آمار کاربران:**\n"
    text += f"├ کل: {stats['total_users']}\n"
    text += f"└ این هفته: {stats['week_new_users']}\n\n"
    
    # Cache
    if cache_stats:
        text += "**💾 Cache:**\n"
        text += f"├ Hit Rate: {cache_stats['hit_rate']}%\n"
        text += f"└ Items: {cache_stats['cache_size']}\n\n"
    
    text += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    # کیبورد
    keyboard = [
        [
            InlineKeyboardButton("📊 آمار کامل", callback_data="dash:full_stats"),
            InlineKeyboardButton("👥 کاربران", callback_data="dash:users")
        ],
        [
            InlineKeyboardButton("🏥 Health Check", callback_data="dash:health"),
            InlineKeyboardButton("💾 Cache", callback_data="dash:cache")
        ],
        [
            InlineKeyboardButton("⚠️ خطاها", callback_data="dash:errors"),
            InlineKeyboardButton("📈 تحلیل", callback_data="dash:analysis")
        ],
        [
            InlineKeyboardButton("🔄 بروزرسانی", callback_data="dash:refresh")
        ]
    ]
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                # متن و keyboard تغییری نکرده - فقط answer بدیم
                await update.callback_query.answer("✅ داشبورد به‌روز است", show_alert=False)
            else:
                # خطای دیگه‌ای بود
                raise
    else:
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_full_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار کامل"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    stats = db.get_statistics()
    
    text = "📊 **آمار کامل سیستم**\n"
    text += "═" * 30 + "\n\n"
    
    # سفارشات
    text += "**📦 سفارشات:**\n"
    text += f"├ کل: {stats['total_orders']}\n"
    text += f"├ امروز: {stats['today_orders']}\n"
    text += f"├ این هفته: {stats['week_orders']}\n"
    text += f"└ در انتظار: {stats['pending_orders']}\n\n"
    
    # درآمد
    text += "**💰 درآمد:**\n"
    text += f"├ کل: {stats['total_income']:,.0f} تومان\n"
    text += f"├ امروز: {stats['today_income']:,.0f} تومان\n"
    text += f"└ هفته: {stats['week_income']:,.0f} تومان\n\n"
    
    # کاربران
    text += "**👥 کاربران:**\n"
    text += f"├ کل: {stats['total_users']}\n"
    text += f"└ جدید (هفته): {stats['week_new_users']}\n\n"
    
    # محصولات
    text += "**🏷 محصولات:**\n"
    text += f"├ تعداد: {stats['total_products']}\n"
    
    # ✅ FIX: Escape کردن نام محصول
    most_popular = escape_markdown(stats['most_popular'])
    text += f"└ محبوب‌ترین: {most_popular}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="dash:main")]]
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ اطلاعات به‌روز است", show_alert=False)
        else:
            raise


async def show_users_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کاربران"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    
    # آمار کاربران
    cursor = db.cursor
    
    # کل کاربران
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    
    # کاربران فعال (دارای سفارش)
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) FROM orders
    """)
    active = cursor.fetchone()[0]
    
    # کاربران امروز
    cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE DATE(created_at) = DATE('now')
    """)
    today = cursor.fetchone()[0]
    
    # آخرین کاربران
    cursor.execute("""
        SELECT user_id, username, first_name, created_at 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    recent_users = cursor.fetchall()
    
    text = "👥 **مدیریت کاربران**\n"
    text += "═" * 30 + "\n\n"
    
    text += f"**📊 آمار:**\n"
    text += f"├ کل: {total}\n"
    text += f"├ فعال: {active}\n"
    text += f"├ غیرفعال: {total - active}\n"
    text += f"└ امروز: {today}\n\n"
    
    text += "**🆕 آخرین کاربران:**\n"
    for user in recent_users:
        user_id, username, first_name, created_at = user
        
        # ✅ FIX: Escape کردن first_name و username
        safe_first_name = escape_markdown(first_name) if first_name else "نامشخص"
        
        if username:
            # @ رو escape نکنیم چون باید به عنوان username باقی بمونه
            safe_username = f"@{escape_markdown(username)}"
        else:
            safe_username = "بدون username"
        
        text += f"├ {safe_first_name} ({safe_username})\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📋 لیست کامل", callback_data="dash:users_list:0"),
            InlineKeyboardButton("📊 گزارش", callback_data="dash:users_report_all")
        ],
        [
            InlineKeyboardButton("🔍 جستجو", callback_data="dash:search_user")
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="dash:main")]
    ]
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ اطلاعات به‌روز است", show_alert=False)
        else:
            raise


async def show_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """نمایش لیست کاربران با صفحه‌بندی"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    
    # دریافت همه کاربران
    all_users = db.get_all_users()
    
    if not all_users:
        await query.edit_message_text("هیچ کاربری ثبت نشده است.")
        return
    
    # تنظیمات صفحه‌بندی
    USERS_PER_PAGE = 5
    total_users = len(all_users)
    total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    
    # اطمینان از معتبر بودن شماره صفحه
    page = max(0, min(page, total_pages - 1))
    
    # محاسبه ایندکس‌ها
    start_idx = page * USERS_PER_PAGE
    end_idx = min(start_idx + USERS_PER_PAGE, total_users)
    
    # کاربران صفحه فعلی
    page_users = all_users[start_idx:end_idx]
    
    text = f"👥 **لیست کاربران** \\(صفحه {page + 1} از {total_pages}\\)\n"
    text += f"📊 مجموع: {total_users} کاربر\n"
    text += "═" * 30 + "\n\n"
    
    for idx, user in enumerate(page_users, start=start_idx + 1):
        user_id = user[0]
        username = user[1]
        first_name = user[2]
        
        # ایجاد نام نمایشی
        safe_name = escape_markdown(first_name) if first_name else f"User {user_id}"
        
        if username:
            display = f"@{escape_markdown(username)}"
        else:
            display = safe_name
        
        # لینک به چت کاربر (برای ادمین)
        chat_link = f"[{display}](tg://user?id={user_id})"
        
        text += f"**{idx}\\.** {chat_link}\n"
        text += f"   └ ID: `{user_id}`\n\n"
    
    # ساخت دکمه‌های صفحه‌بندی
    keyboard = []
    
    # دکمه‌های قبل/بعد
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"dash:users_list:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"dash:users_list:{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # دکمه گزارش
    keyboard.append([InlineKeyboardButton("📊 گزارش کامل", callback_data="dash:users_report_all")])
    
    # دکمه بازگشت
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="dash:users")])
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ در این صفحه هستید", show_alert=False)
        else:
            raise


async def show_users_report_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """گزارش کامل همه کاربران"""
    query = update.callback_query
    await query.answer("در حال تهیه گزارش...", show_alert=False)
    
    db = context.bot_data['db']
    
    # دریافت همه کاربران
    all_users = db.get_all_users()
    
    if not all_users:
        await query.edit_message_text("هیچ کاربری ثبت نشده است.")
        return
    
    text = f"📊 **گزارش کامل کاربران**\n"
    text += f"تعداد کل: {len(all_users)} نفر\n"
    text += "═" * 30 + "\n\n"
    
    for idx, user in enumerate(all_users, start=1):
        user_id = user[0]
        username = user[1]
        first_name = user[2]
        full_name = user[3] if len(user) > 3 else None
        phone = user[4] if len(user) > 4 else None
        address = user[6] if len(user) > 6 else None
        shop_name = user[7] if len(user) > 7 else None
        
        # نام نمایشی
        safe_name = escape_markdown(first_name) if first_name else f"User {user_id}"
        
        if username:
            display = f"@{escape_markdown(username)}"
        else:
            display = safe_name
        
        # لینک به چت
        chat_link = f"[{display}](tg://user?id={user_id})"
        
        text += f"**{idx}\\.** {chat_link}\n"
        text += f"├ ID: `{user_id}`\n"
        
        if full_name:
            text += f"├ نام کامل: {escape_markdown(full_name)}\n"
        
        if shop_name:
            text += f"├ نام فروشگاه: {escape_markdown(shop_name)}\n"
        
        if phone:
            text += f"├ موبایل: `{phone}`\n"
        
        if address:
            addr_short = address[:30] + "..." if len(address) > 30 else address
            text += f"└ آدرس: {escape_markdown(addr_short)}\n"
        else:
            text += f"└ آدرس: ثبت نشده\n"
        
        text += "\n"
        
        # محدودیت طول پیام تلگرام (4096 کاراکتر)
        if len(text) > 3500:
            text += f"\n⚠️ **تعداد بیشتر از {idx} کاربر وجود دارد\\.**\n"
            text += "برای مشاهده کامل از لیست صفحه\\-بندی استفاده کنید\\."
            break
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="dash:users_list:0")]]
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ گزارش به‌روز است", show_alert=False)
        else:
            raise


async def show_health_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش وضعیت سلامت سیستم"""
    query = update.callback_query
    await query.answer()
    
    health_checker = context.bot_data.get('health_checker')
    
    if not health_checker:
        await query.answer("Health Checker فعال نیست!", show_alert=True)
        return
    
    # دریافت گزارش
    report = health_checker.get_health_report()
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="dash:main")]]
    
    try:
        await query.edit_message_text(
            report,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ اطلاعات به‌روز است", show_alert=False)
        else:
            raise


async def show_cache_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار کش"""
    query = update.callback_query
    await query.answer()
    
    cache_manager = context.bot_data.get('cache_manager')
    
    if not cache_manager:
        await query.answer("Cache Manager فعال نیست!", show_alert=True)
        return
    
    stats = cache_manager.get_stats()
    
    text = "💾 **آمار Cache**\n"
    text += "═" * 30 + "\n\n"
    
    text += f"**📊 عملکرد:**\n"
    text += f"├ Hit Rate: {stats['hit_rate']}%\n"
    text += f"├ Hits: {stats['hits']}\n"
    text += f"├ Misses: {stats['misses']}\n"
    text += f"└ Total Requests: {stats['total_requests']}\n\n"
    
    text += f"**💾 ذخیره‌سازی:**\n"
    text += f"├ Items: {stats['cache_size']}\n"
    text += f"├ Sets: {stats['sets']}\n"
    text += f"├ Invalidations: {stats['invalidations']}\n"
    text += f"└ Expirations: {stats['expirations']}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("🗑 پاک کردن", callback_data="dash:cache_clear"),
            InlineKeyboardButton("🧹 پاکسازی", callback_data="dash:cache_cleanup")
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="dash:main")]
    ]
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ اطلاعات به‌روز است", show_alert=False)
        else:
            raise


async def show_errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش خطاهای اخیر"""
    query = update.callback_query
    await query.answer()
    
    health_checker = context.bot_data.get('health_checker')
    
    if not health_checker:
        await query.answer("Health Checker فعال نیست!", show_alert=True)
        return
    
    errors = health_checker.last_errors[-10:]
    
    text = "⚠️ **آخرین خطاها**\n"
    text += "═" * 30 + "\n\n"
    
    if not errors:
        text += "✅ خطایی ثبت نشده است!"
    else:
        for idx, err in enumerate(errors, 1):
            # ✅ FIX: Escape کردن error type و message
            error_type = escape_markdown(err['type'])
            error_msg = escape_markdown(err['message'][:50])
            
            text += f"**{idx}\\. {error_type}**\n"
            text += f"├ پیام: {error_msg}\\.\\.\\.\n"
            text += f"├ زمان: {err['timestamp'][11:19]}\n"
            if err.get('user_id'):
                text += f"└ کاربر: {err['user_id']}\n"
            text += "\n"
    
    # آمار خطاها
    error_handler = context.bot_data.get('error_handler')
    if error_handler:
        error_stats = error_handler.get_error_stats()
        text += f"\n**📊 آمار:**\n"
        text += f"└ کل خطاها: {error_stats['total_errors']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="dash:main")]]
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ اطلاعات به‌روز است", show_alert=False)
        else:
            raise


async def show_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحلیل و گزارش‌ها"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    cursor = db.cursor
    
    # تحلیل فروش
    cursor.execute("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as orders,
            SUM(final_price) as revenue
        FROM orders
        WHERE created_at >= DATE('now', '-7 days')
        AND status IN ('confirmed', 'payment_confirmed')
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """)
    sales_data = cursor.fetchall()
    
    # محبوب‌ترین ساعت سفارش
    cursor.execute("""
        SELECT strftime('%H', created_at) as hour, COUNT(*) as count
        FROM orders
        WHERE created_at >= DATE('now', '-30 days')
        GROUP BY hour
        ORDER BY count DESC
        LIMIT 3
    """)
    peak_hours = cursor.fetchall()
    
    text = "📈 **تحلیل و بررسی**\n"
    text += "═" * 30 + "\n\n"
    
    text += "**📊 فروش 7 روز اخیر:**\n"
    if sales_data:
        for date, orders, revenue in sales_data[:5]:
            text += f"├ {date}: {orders} سفارش، {revenue:,.0f} تومان\n"
    else:
        text += "├ داده‌ای موجود نیست\n"
    
    text += "\n**⏰ ساعات شلوغ:**\n"
    for hour, count in peak_hours:
        text += f"├ {hour}:00 \\- {count} سفارش\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 گزارش کامل", callback_data="analytics:sales_weekly")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="dash:main")]
    ]
    
    try:
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ اطلاعات به‌روز است", show_alert=False)
        else:
            raise


async def cache_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاک کردن کامل کش"""
    query = update.callback_query
    
    cache_manager = context.bot_data.get('cache_manager')
    
    if cache_manager:
        cache_manager.clear()
        await query.answer("✅ کش پاک شد!", show_alert=True)
        log_admin_action(update.effective_user.id, "Cache Clear", "تمام کش پاک شد")
    else:
        await query.answer("❌ Cache Manager فعال نیست!", show_alert=True)
    
    # بازگشت به صفحه کش
    await show_cache_stats(update, context)


async def cache_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاکسازی کش‌های منقضی"""
    query = update.callback_query
    
    cache_manager = context.bot_data.get('cache_manager')
    
    if cache_manager:
        cache_manager.cleanup()
        await query.answer("✅ پاکسازی انجام شد!", show_alert=True)
    else:
        await query.answer("❌ Cache Manager فعال نیست!", show_alert=True)
    
    # بازگشت به صفحه کش
    await show_cache_stats(update, context)


async def handle_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت callback های داشبورد"""
    query = update.callback_query
    data = query.data
    
    if data == "dash:main":
        await admin_dashboard(update, context)
    elif data == "dash:full_stats":
        await show_full_stats(update, context)
    elif data == "dash:users":
        await show_users_management(update, context)
    elif data.startswith("dash:users_list:"):
        # صفحه‌بندی لیست کاربران
        page = int(data.split(":")[-1])
        await show_users_list(update, context, page)
    elif data == "dash:users_report_all":
        await show_users_report_all(update, context)
    elif data == "dash:health":
        await show_health_status(update, context)
    elif data == "dash:cache":
        await show_cache_stats(update, context)
    elif data == "dash:errors":
        await show_errors(update, context)
    elif data == "dash:analysis":
        await show_analysis(update, context)
    elif data == "dash:refresh":
        await admin_dashboard(update, context)
    elif data == "dash:cache_clear":
        await cache_clear(update, context)
    elif data == "dash:cache_cleanup":
        await cache_cleanup(update, context)
