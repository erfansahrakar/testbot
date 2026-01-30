"""
مدیریت تخفیف‌ها - نسخه اصلاح شده ✅

"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from validators import Validators
from states import (
    DISCOUNT_CODE, DISCOUNT_TYPE, DISCOUNT_VALUE,
    DISCOUNT_MIN_PURCHASE, DISCOUNT_MAX, DISCOUNT_LIMIT,
    DISCOUNT_PER_USER_LIMIT,
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
import logging

logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def calculate_discount(total_price: float, discount_code: str, db, user_id: int = None) -> tuple:
    """
    محاسبه تخفیف با چک Division by Zero و Validation کامل
    ✅ NEW: اضافه شدن چک محدودیت به ازای هر کاربر
    
    Args:
        total_price: مبلغ کل خرید
        discount_code: کد تخفیف
        db: نمونه دیتابیس
        user_id: شناسه کاربر (برای چک محدودیت شخصی)
    
    Returns:
        (discount_amount, final_price, error_message)
    """
    if total_price <= 0:
        return 0, total_price, "❌ مبلغ خرید نامعتبر است!"
    
    discount_info = db.get_discount(discount_code)
    
    if not discount_info:
        return 0, total_price, "❌ کد تخفیف نامعتبر است!"
    
    # ✅ UPDATED: اضافه شدن per_user_limit به unpacking
    discount_id, code, discount_type, value, min_purchase, max_discount, usage_limit, used_count, per_user_limit, start_date, end_date, is_active, created_at = discount_info
    
    if not is_active:
        return 0, total_price, "❌ این کد تخفیف غیرفعال است!"
    
    now = datetime.now()
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            if now < start_dt:
                return 0, total_price, "❌ این کد تخفیف هنوز فعال نشده است!"
        except (ValueError, TypeError):
            logger.error(f"Invalid start_date format: {start_date}")
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            if now > end_dt:
                return 0, total_price, "❌ این کد تخفیف منقضی شده است!"
        except (ValueError, TypeError):
            logger.error(f"Invalid end_date format: {end_date}")
    
    if usage_limit and used_count >= usage_limit:
        return 0, total_price, "❌ این کد تخفیف به حداکثر تعداد استفاده رسیده است!"
    
    # ✅ NEW: چک محدودیت به ازای هر کاربر
    if per_user_limit and user_id:
        user_usage_count = db.get_user_discount_usage_count(user_id, discount_code)
        if user_usage_count >= per_user_limit:
            return 0, total_price, f"❌ شما قبلاً {per_user_limit} بار از این کد استفاده کرده‌اید!"
    
    if min_purchase > 0 and total_price < min_purchase:
        return 0, total_price, f"❌ حداقل خرید برای این کد {min_purchase:,.0f} تومان است!"
    
    discount_amount = 0
    
    if discount_type == 'percentage':
        if value <= 0 or value > 100:
            logger.error(f"Invalid percentage value: {value}")
            return 0, total_price, "❌ درصد تخفیف نامعتبر است!"
        
        discount_amount = total_price * (value / 100)
        
        if max_discount and discount_amount > max_discount:
            discount_amount = max_discount
    
    else:  # fixed amount
        if value <= 0:
            logger.error(f"Invalid fixed discount value: {value}")
            return 0, total_price, "❌ مبلغ تخفیف نامعتبر است!"
        
        discount_amount = value
        
        if discount_amount > total_price:
            discount_amount = total_price
    
    final_price = round(total_price - discount_amount, 2)
    
    if final_price < 0:
        final_price = 0
    
    return discount_amount, final_price, None


# ==================== Admin Handlers ====================

async def discount_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی مدیریت تخفیف‌ها"""
    logger.info("📋 discount_menu called")
    
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"⛔ Unauthorized access attempt by {update.effective_user.id}")
        return
    
    try:
        await update.message.reply_text(
            "🎁 **مدیریت کدهای تخفیف**\n\n"
            "از منوی زیر انتخاب کنید:",
            parse_mode='Markdown',
            reply_markup=discount_management_keyboard()
        )
        logger.info("✅ discount_menu displayed successfully")
    except Exception as e:
        logger.error(f"❌ Error in discount_menu: {e}", exc_info=True)


async def create_discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ایجاد کد تخفیف"""
    logger.info("🎫 create_discount_start called")
    
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        logger.warning(f"⛔ Unauthorized access attempt by {update.effective_user.id}")
        return ConversationHandler.END
    
    try:
        await query.message.reply_text(
            "📝 **ایجاد کد تخفیف جدید**\n\n"
            "لطفاً کد تخفیف را وارد کنید:\n"
            "مثال: SUMMER2024",
            parse_mode='Markdown',
            reply_markup=cancel_keyboard()
        )
        logger.info("✅ create_discount_start - waiting for discount code")
        return DISCOUNT_CODE
    except Exception as e:
        logger.error(f"❌ Error in create_discount_start: {e}", exc_info=True)
        return ConversationHandler.END


async def discount_code_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت کد تخفیف"""
    logger.info(f"📝 discount_code_received: {update.message.text}")
    
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    code = update.message.text
    
    is_valid, error_msg, cleaned_code = Validators.validate_discount_code(code)
    
    if not is_valid:
        logger.warning(f"❌ Invalid discount code: {code}")
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_CODE
    
    db = context.bot_data['db']
    existing = db.get_discount(cleaned_code)
    
    if existing:
        logger.warning(f"❌ Duplicate discount code: {cleaned_code}")
        await update.message.reply_text(
            "❌ این کد قبلاً استفاده شده است!\n"
            "لطفاً کد دیگری وارد کنید:",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_CODE
    
    context.user_data['discount_code'] = cleaned_code
    
    try:
        await update.message.reply_text(
            "💯 نوع تخفیف را انتخاب کنید:",
            reply_markup=discount_type_keyboard()
        )
        logger.info(f"✅ Discount code saved: {cleaned_code}, waiting for type selection")
        return DISCOUNT_TYPE
    except Exception as e:
        logger.error(f"❌ Error sending discount_type_keyboard: {e}", exc_info=True)
        return ConversationHandler.END


async def discount_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب نوع تخفیف"""
    logger.info("💯 discount_type_selected called")
    
    query = update.callback_query
    
    try:
        await query.answer()
        logger.info(f"📞 Callback data: {query.data}")
        
        discount_type = query.data.split(":")[1]
        context.user_data['discount_type'] = discount_type
        
        logger.info(f"✅ Discount type selected: {discount_type}")
        
        if discount_type == "percentage":
            await query.message.reply_text(
                "💯 درصد تخفیف را وارد کنید:\n"
                "مثال: 10 (برای 10 درصد)\n\n"
                "⚠️ باید بین 1 تا 100 باشد",
                reply_markup=cancel_keyboard()
            )
        else:
            await query.message.reply_text(
                "💰 مبلغ تخفیف را به تومان وارد کنید:\n"
                "مثال: 50000\n\n"
                "⚠️ حداقل 1000 تومان",
                reply_markup=cancel_keyboard()
            )
        
        logger.info("✅ Waiting for discount value")
        return DISCOUNT_VALUE
        
    except Exception as e:
        logger.error(f"❌ Error in discount_type_selected: {e}", exc_info=True)
        await query.message.reply_text(
            "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        return ConversationHandler.END


async def discount_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت مقدار تخفیف"""
    logger.info(f"💰 discount_value_received: {update.message.text}")
    
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    value_str = update.message.text
    discount_type = context.user_data['discount_type']
    
    if discount_type == "percentage":
        is_valid, error_msg, value = Validators.validate_quantity(value_str, min_value=1, max_value=100)
        
        if not is_valid:
            await update.message.reply_text(
                "❌ درصد تخفیف باید بین 1 تا 100 باشد!\n"
                "لطفاً دوباره وارد کنید:",
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_VALUE
        
        is_valid_pct, error_pct = Validators.validate_percentage(value)
        if not is_valid_pct:
            await update.message.reply_text(
                error_pct,
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_VALUE
    
    else:
        is_valid, error_msg, value = Validators.validate_price(value_str)
        
        if not is_valid or value < 1000:
            await update.message.reply_text(
                "❌ مبلغ تخفیف باید حداقل 1000 تومان باشد!\n"
                "لطفاً دوباره وارد کنید:",
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_VALUE
    
    context.user_data['discount_value'] = value
    
    await update.message.reply_text(
        "💳 حداقل مبلغ خرید برای استفاده از این کد:\n"
        "(برای نداشتن محدودیت عدد 0 وارد کنید)\n\n"
        "مثال: 100000",
        reply_markup=cancel_keyboard()
    )
    
    return DISCOUNT_MIN_PURCHASE


async def discount_min_purchase_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت حداقل خرید"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    is_valid, error_msg, min_purchase = Validators.validate_price(update.message.text)
    
    if not is_valid:
        await update.message.reply_text(
            "❌ لطفاً یک عدد صحیح وارد کنید!",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_MIN_PURCHASE
    
    context.user_data['discount_min_purchase'] = min_purchase if min_purchase > 0 else 0
    
    if context.user_data['discount_type'] == "percentage":
        await update.message.reply_text(
            "🔝 حداکثر مبلغ تخفیف (تومان):\n"
            "(برای نداشتن محدودیت عدد 0 وارد کنید)\n\n"
            "مثال: 50000",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_MAX
    else:
        await update.message.reply_text(
            "🔢 محدودیت تعداد استفاده:\n"
            "(برای نامحدود عدد 0 وارد کنید)\n\n"
            "مثال: 100",
            reply_markup=cancel_keyboard()
        )
        context.user_data['discount_max'] = None
        return DISCOUNT_LIMIT


async def discount_max_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت حداکثر تخفیف"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    is_valid, error_msg, max_discount = Validators.validate_price(update.message.text)
    
    if not is_valid:
        await update.message.reply_text(
            "❌ لطفاً یک عدد صحیح وارد کنید!",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_MAX
    
    context.user_data['discount_max'] = max_discount if max_discount > 0 else None
    
    await update.message.reply_text(
        "🔢 محدودیت تعداد استفاده:\n"
        "(برای نامحدود عدد 0 وارد کنید)\n\n"
        "مثال: 100",
        reply_markup=cancel_keyboard()
    )
    
    return DISCOUNT_LIMIT


async def discount_limit_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت محدودیت استفاده کل"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    try:
        usage_limit = int(update.message.text)
        
        if usage_limit < 0:
            await update.message.reply_text(
                "❌ تعداد نمی‌تواند منفی باشد!",
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_LIMIT
        
        context.user_data['discount_limit'] = usage_limit if usage_limit > 0 else None
        
        await update.message.reply_text(
            "👤 محدودیت استفاده به ازای هر کاربر:\n"
            "(هر نفر چند بار می‌تواند از این کد استفاده کند؟)\n"
            "(برای نامحدود عدد 0 وارد کنید)\n\n"
            "مثال: 3 (هر نفر فقط ۳ بار)",
            reply_markup=cancel_keyboard()
        )
        
        return DISCOUNT_PER_USER_LIMIT
        
    except ValueError:
        await update.message.reply_text(
            "❌ لطفاً یک عدد صحیح وارد کنید!",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_LIMIT


async def discount_per_user_limit_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت محدودیت استفاده به ازای هر کاربر"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    try:
        per_user_limit = int(update.message.text)
        
        if per_user_limit < 0:
            await update.message.reply_text(
                "❌ تعداد نمی‌تواند منفی باشد!",
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_PER_USER_LIMIT
        
        context.user_data['discount_per_user_limit'] = per_user_limit if per_user_limit > 0 else None
        
        await update.message.reply_text(
            "📅 تاریخ شروع اعتبار را وارد کنید:\n"
            "(فرمت: YYYY-MM-DD مثل 2024-12-25)\n"
            "(برای شروع فوری عدد 0 وارد کنید)",
            reply_markup=cancel_keyboard()
        )
        
        return DISCOUNT_START
        
    except ValueError:
        await update.message.reply_text(
            "❌ لطفاً یک عدد صحیح وارد کنید!",
            reply_markup=cancel_keyboard()
        )
        return DISCOUNT_PER_USER_LIMIT


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
                "مثال: 2024-12-25",
                reply_markup=cancel_keyboard()
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
                "مثال: 2024-12-31",
                reply_markup=cancel_keyboard()
            )
            return DISCOUNT_END
    
    db = context.bot_data['db']
    
    try:
        db.create_discount(
            code=context.user_data['discount_code'],
            type=context.user_data['discount_type'],
            value=context.user_data['discount_value'],
            min_purchase=context.user_data.get('discount_min_purchase', 0),
            max_discount=context.user_data.get('discount_max'),
            usage_limit=context.user_data.get('discount_limit'),
            per_user_limit=context.user_data.get('discount_per_user_limit'),
            start_date=context.user_data.get('discount_start'),
            end_date=end_date
        )
    except Exception as e:
        logger.error(f"❌ Error creating discount: {e}")
        await update.message.reply_text(
            "❌ خطا در ایجاد کد تخفیف!",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
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
        summary += f"🔢 محدودیت کل: {context.user_data['discount_limit']} بار\n"
    
    if context.user_data.get('discount_per_user_limit'):
        summary += f"👤 محدودیت هر کاربر: {context.user_data['discount_per_user_limit']} بار\n"
    
    if context.user_data.get('discount_start'):
        summary += f"📅 شروع: {context.user_data['discount_start'][:10]}\n"
    
    if end_date:
        summary += f"📅 پایان: {end_date[:10]}\n"
    
    await update.message.reply_text(
        summary,
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )
    
    context.user_data.clear()
    
    return ConversationHandler.END


async def list_discounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست تخفیف‌ها"""
    logger.info("📋 list_discounts called")
    
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
    
    discount_id, code, type, value, min_purchase, max_discount, usage_limit, used_count, per_user_limit, start_date, end_date, is_active, created_at = discount
    
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
    
    text += f"\n🔢 استفاده کل: {used_count}"
    if usage_limit:
        text += f" از {usage_limit}"
    else:
        text += " (نامحدود)"
    
    if per_user_limit:
        text += f"\n👤 محدودیت هر کاربر: {per_user_limit} بار"
    
    if start_date:
        try:
            text += f"\n📅 شروع: {start_date[:10]}"
        except (TypeError, AttributeError):
            pass
    
    if end_date:
        try:
            text += f"\n📅 پایان: {end_date[:10]}"
        except (TypeError, AttributeError):
            pass
    
    if created_at:
        try:
            text += f"\n\n📆 ایجاد شده: {created_at[:10]}"
        except (TypeError, AttributeError):
            pass
    
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
