"""
مدیریت تخفیف‌ها
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from validators import Validators
from states import (
    DISCOUNT_CODE, DISCOUNT_TYPE, DISCOUNT_VALUE,
    DISCOUNT_MIN_PURCHASE, DISCOUNT_MAX, DISCOUNT_LIMIT,
    DISCOUNT_START, DISCOUNT_END
)
from keyboards import (
    discount_management_keyboard,
    discount_list_keyboard,
    discount_detail_keyboard,
    discount_type_keyboard,
    cancel_keyboard,
    admin_main_keyboard
)
from datetime import datetime


async def discount_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی مدیریت تخفیف‌ها"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    await update.message.reply_text(
        "🎁 **مدیریت کدهای تخفیف**\n\n"
        "از منوی زیر انتخاب کنید:",
        parse_mode='Markdown',
        reply_markup=discount_management_keyboard()
    )


async def create_discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ایجاد کد تخفیف"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    await query.message.reply_text(
        "📝 **ایجاد کد تخفیف جدید**\n\n"
        "لطفاً کد تخفیف را وارد کنید:\n"
        "مثال: SUMMER2024",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return DISCOUNT_CODE


async def discount_code_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت کد تخفیف - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    code = update.message.text
    
    # 🔒 اعتبارسنجی کد تخفیف
    is_valid, error_msg, cleaned_code = Validators.validate_discount_code(code)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_CODE  # دوباره بپرس
    
    # بررسی تکراری نبودن
    db = context.bot_data['db']
    existing = db.get_discount(cleaned_code)
    
    if existing:
        await update.message.reply_text(
            "❌ این کد قبلاً استفاده شده است!\n"
            "لطفاً کد دیگری وارد کنید:",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_CODE
    
    context.user_data['discount_code'] = cleaned_code
    
    await update.message.reply_text(
        "💯 نوع تخفیف را انتخاب کنید:",
        reply_markup=discount_type_keyboard()
    )
    
    return DISCOUNT_TYPE


async def discount_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب نوع تخفیف"""
    query = update.callback_query
    await query.answer()
    
    discount_type = query.data.split(":")[1]
    context.user_data['discount_type'] = discount_type
    
    if discount_type == "percentage":
        await query.message.reply_text(
            "💯 درصد تخفیف را وارد کنید:\n"
            "مثال: 10 (برای 10 درصد)",
            reply_markup=cancel_keyboard()
        )
    else:
        await query.message.reply_text(
            "💰 مبلغ تخفیف را به تومان وارد کنید:\n"
            "مثال: 50000",
            reply_markup=cancel_keyboard()
        )
    
    return DISCOUNT_VALUE


async def discount_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مقدار تخفیف - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    value_str = update.message.text
    discount_type = context.user_data['discount_type']
    
    # 🔒 اعتبارسنجی مقدار
    if discount_type == "percentage":
        # برای درصد
        is_valid, error_msg, value = Validators.validate_quantity(value_str, min_value=1, max_value=100)
        
        if not is_valid:
            await update.message.reply_text(
                "❌ درصد تخفیف باید بین 1 تا 100 باشد!",
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_VALUE
        
        # بررسی اضافی برای درصد
        is_valid_pct, error_pct = Validators.validate_percentage(value)
        if not is_valid_pct:
            await update.message.reply_text(
                error_pct,
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_VALUE
            
    else:
        # برای مبلغ ثابت
        is_valid, error_msg, value = Validators.validate_price(value_str, min_value=1000)
        
        if not is_valid:
            await update.message.reply_text(
                error_msg,
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_VALUE
    
    context.user_data['discount_value'] = value
    
    await update.message.reply_text(
        "💳 حداقل مبلغ خرید را به تومان وارد کنید:\n"
        "(برای بدون محدودیت عدد 0 وارد کنید)\n"
        "مثال: 100000",
        reply_markup=cancel_keyboard()
    )
    
    return DISCOUNT_MIN_PURCHASE

async def discount_min_purchase_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت حداقل خرید - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    min_purchase_str = update.message.text
    
    # 🔒 اعتبارسنجی
    is_valid, error_msg, min_purchase = Validators.validate_price(min_purchase_str, min_value=0)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_MIN_PURCHASE
    
    context.user_data['discount_min_purchase'] = min_purchase
    
    if context.user_data['discount_type'] == "percentage":
        await update.message.reply_text(
            "🔝 حداکثر مبلغ تخفیف را به تومان وارد کنید:\n"
            "(برای بدون محدودیت عدد 0 وارد کنید)\n"
            "مثال: 200000",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_MAX
    else:
        # تخفیف ثابت حداکثر ندارد
        context.user_data['discount_max'] = None
        await update.message.reply_text(
            "🔢 محدودیت تعداد استفاده را وارد کنید:\n"
            "(برای نامحدود عدد 0 وارد کنید)\n"
            "مثال: 100",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_LIMIT


async def discount_max_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت حداکثر تخفیف"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    try:
        max_discount = float(update.message.text.replace(',', ''))
        context.user_data['discount_max'] = max_discount if max_discount > 0 else None
        
        await update.message.reply_text(
            "🔢 محدودیت تعداد استفاده را وارد کنید:\n"
            "(برای نامحدود عدد 0 وارد کنید)\n"
            "مثال: 100",
            reply_markup=cancel_keyboard()
        )
        
        return DISCOUNT_LIMIT
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return DISCOUNT_MAX


async def discount_limit_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت محدودیت استفاده"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    try:
        usage_limit = int(update.message.text)
        context.user_data['discount_limit'] = usage_limit if usage_limit > 0 else None
        
        await update.message.reply_text(
            "📅 تاریخ شروع اعتبار را وارد کنید:\n"
            "(فرمت: YYYY-MM-DD مثل 2024-12-25)\n"
            "(برای شروع فوری عدد 0 وارد کنید)",
            reply_markup=cancel_keyboard()
        )
        
        return DISCOUNT_START
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد صحیح وارد کنید!")
        return DISCOUNT_LIMIT


async def discount_start_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تاریخ شروع"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    text = update.message.text.strip()
    
    if text == "0":
        context.user_data['discount_start'] = None
    else:
        try:
            start_date = datetime.strptime(text, "%Y-%m-%d")
            context.user_data['discount_start'] = start_date.isoformat()
        except ValueError:
            await update.message.reply_text(
                "❌ فرمت تاریخ نادرست است!\n"
                "لطفاً به فرمت YYYY-MM-DD وارد کنید:\n"
                "مثال: 2024-12-25"
            )
            return DISCOUNT_START
    
    await update.message.reply_text(
        "📅 تاریخ پایان اعتبار را وارد کنید:\n"
        "(فرمت: YYYY-MM-DD مثل 2024-12-31)\n"
        "(برای بدون تاریخ انقضا عدد 0 وارد کنید)",
        reply_markup=cancel_keyboard()
    )
    
    return DISCOUNT_END


async def discount_end_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تاریخ پایان و ذخیره تخفیف"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    text = update.message.text.strip()
    
    if text == "0":
        end_date = None
    else:
        try:
            end_date_obj = datetime.strptime(text, "%Y-%m-%d")
            end_date = end_date_obj.isoformat()
        except ValueError:
            await update.message.reply_text(
                "❌ فرمت تاریخ نادرست است!\n"
                "لطفاً به فرمت YYYY-MM-DD وارد کنید:\n"
                "مثال: 2024-12-31"
            )
            return DISCOUNT_END
    
    # ذخیره در دیتابیس
    db = context.bot_data['db']
    db.create_discount(
        code=context.user_data['discount_code'],
        type=context.user_data['discount_type'],
        value=context.user_data['discount_value'],
        min_purchase=context.user_data.get('discount_min_purchase', 0),
        max_discount=context.user_data.get('discount_max'),
        usage_limit=context.user_data.get('discount_limit'),
        start_date=context.user_data.get('discount_start'),
        end_date=end_date
    )
    
    # نمایش خلاصه
    summary = "✅ **کد تخفیف ایجاد شد!**\n\n"
    summary += f"🎫 کد: `{context.user_data['discount_code']}`\n"
    
    if context.user_data['discount_type'] == "percentage":
        summary += f"💯 نوع: {context.user_data['discount_value']}% تخفیف\n"
        if context.user_data.get('discount_max'):
            summary += f"🔝 حداکثر: {context.user_data['discount_max']:,.0f} تومان\n"
    else:
        summary += f"💰 نوع: {context.user_data['discount_value']:,.0f} تومان تخفیف\n"
    
    if context.user_data.get('discount_min_purchase', 0) > 0:
        summary += f"💳 حداقل خرید: {context.user_data['discount_min_purchase']:,.0f} تومان\n"
    
    if context.user_data.get('discount_limit'):
        summary += f"🔢 محدودیت: {context.user_data['discount_limit']} بار\n"
    
    if context.user_data.get('discount_start'):
        summary += f"📅 شروع: {context.user_data['discount_start'][:10]}\n"
    
    if end_date:
        summary += f"📅 پایان: {end_date[:10]}\n"
    
    await update.message.reply_text(
        summary,
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )
    
    # پاک کردن داده‌های موقت
    context.user_data.clear()
    
    return ConversationHandler.END


async def list_discounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست تخفیف‌ها"""
    query = update.callback_query
    await query.answer()
    
    db = context.bot_data['db']
    discounts = db.get_all_discounts()
    
    if not discounts:
        await query.message.reply_text(
            "📋 هیچ کد تخفیفی وجود ندارد!",
            reply_markup=discount_management_keyboard()
        )
        return
    
    await query.message.reply_text(
        "📋 **لیست کدهای تخفیف:**\n\n"
        "✅ فعال | ❌ غیرفعال",
        parse_mode='Markdown',
        reply_markup=discount_list_keyboard(discounts)
    )


async def view_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش جزئیات یک تخفیف"""
    query = update.callback_query
    await query.answer()
    
    discount_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    discount = db.cursor.execute(
        "SELECT * FROM discount_codes WHERE id = ?",
        (discount_id,)
    ).fetchone()
    
    if not discount:
        await query.answer("❌ تخفیف یافت نشد!", show_alert=True)
        return
    
    discount_id, code, type, value, min_purchase, max_discount, usage_limit, used_count, start_date, end_date, is_active, created_at = discount
    
    text = f"🎫 **کد تخفیف: {code}**\n\n"
    text += f"📊 وضعیت: {'✅ فعال' if is_active else '❌ غیرفعال'}\n\n"
    
    if type == "percentage":
        text += f"💯 نوع: {value}% تخفیف\n"
        if max_discount:
            text += f"🔝 حداکثر: {max_discount:,.0f} تومان\n"
    else:
        text += f"💰 نوع: {value:,.0f} تومان تخفیف\n"
    
    if min_purchase > 0:
        text += f"💳 حداقل خرید: {min_purchase:,.0f} تومان\n"
    
    text += f"\n🔢 استفاده: {used_count}"
    if usage_limit:
        text += f" از {usage_limit}"
    else:
        text += " (نامحدود)"
    
    if start_date:
        text += f"\n📅 شروع: {start_date[:10]}"
    
    if end_date:
        text += f"\n📅 پایان: {end_date[:10]}"
    
    text += f"\n\n📆 ایجاد شده: {created_at[:10]}"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=discount_detail_keyboard(discount_id)
    )


async def toggle_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال/غیرفعال کردن تخفیف"""
    query = update.callback_query
    
    discount_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    db.toggle_discount(discount_id)
    
    await query.answer("✅ وضعیت تغییر کرد!")
    
    # نمایش مجدد جزئیات
    context.user_data['temp_callback'] = f"view_discount:{discount_id}"
    await view_discount(update, context)


async def delete_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف کد تخفیف"""
    query = update.callback_query
    
    discount_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    db.delete_discount(discount_id)
    
    await query.answer("✅ کد تخفیف حذف شد!")
    await query.edit_message_text("🗑 کد تخفیف حذف شد.")
