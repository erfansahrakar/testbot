"""
🆕 هندلرهای مربوط به اعمال کد تخفیف توسط کاربر
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
from rate_limiter import action_limit
from states import ENTER_DISCOUNT_CODE
from keyboards import cancel_keyboard, user_main_keyboard, cart_keyboard
import json


async def apply_discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع وارد کردن کد تخفیف"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "🎁 **وارد کردن کد تخفیف**\n\n"
        "لطفاً کد تخفیف خود را وارد کنید:",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return ENTER_DISCOUNT_CODE


@action_limit('discount', max_requests=5, window_seconds=60)
async def discount_code_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی و اعمال کد تخفیف"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=user_main_keyboard())
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    discount_code = update.message.text.strip().upper()
    db = context.bot_data['db']
    
    # بررسی سبد خرید
    cart = db.get_cart(user_id)
    if not cart:
        await update.message.reply_text(
            "❌ سبد خرید شما خالی است!",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END
    
    # محاسبه مبلغ کل سبد
    total_price = sum(item[4] * item[5] for item in cart)
    
    # بررسی کد تخفیف
    discount = db.get_discount(discount_code)
    
    if not discount:
        await update.message.reply_text(
            "❌ کد تخفیف نامعتبر است!\n\n"
            "لطفاً کد را دوباره چک کنید یا با پشتیبانی تماس بگیرید.",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END
    
    # بررسی اعتبار کد
    discount_id, code, disc_type, value, min_purchase, max_discount, usage_limit, used_count, start_date, end_date, is_active, created_at = discount
    
    # بررسی فعال بودن
    if not is_active:
        await update.message.reply_text(
            "❌ این کد تخفیف غیرفعال شده است!",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END
    
    # بررسی تاریخ شروع
    if start_date:
        start = datetime.fromisoformat(start_date)
        if datetime.now() < start:
            await update.message.reply_text(
                f"❌ این کد تخفیف از تاریخ {start_date[:10]} فعال می‌شود!",
                reply_markup=user_main_keyboard()
            )
            return ConversationHandler.END
    
    # بررسی تاریخ انقضا
    if end_date:
        end = datetime.fromisoformat(end_date)
        if datetime.now() > end:
            await update.message.reply_text(
                "❌ این کد تخفیف منقضی شده است!",
                reply_markup=user_main_keyboard()
            )
            return ConversationHandler.END
    
    # بررسی محدودیت استفاده
    if usage_limit and used_count >= usage_limit:
        await update.message.reply_text(
            "❌ این کد تخفیف به حداکثر تعداد استفاده رسیده است!",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END
    
    # بررسی حداقل خرید
    if total_price < min_purchase:
        await update.message.reply_text(
            f"❌ برای استفاده از این کد تخفیف، حداقل خرید {min_purchase:,.0f} تومان الزامی است!\n\n"
            f"💰 مبلغ فعلی سبد شما: {total_price:,.0f} تومان",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END
    
    # محاسبه تخفیف
    discount_amount = 0
    
    if disc_type == 'percentage':
        discount_amount = total_price * (value / 100)
        if max_discount and discount_amount > max_discount:
            discount_amount = max_discount
    else:  # fixed
        discount_amount = value
    
    # محاسبه مبلغ نهایی
    final_price = total_price - discount_amount
    
    if final_price < 0:
        final_price = 0
    
    # ذخیره کد تخفیف در context برای استفاده موقع ثبت سفارش
    context.user_data['applied_discount_code'] = discount_code
    context.user_data['discount_amount'] = discount_amount
    context.user_data['discount_id'] = discount_id
    
    # نمایش سبد با تخفیف
    text = "✅ **کد تخفیف اعمال شد!**\n\n"
    text += "🛒 **سبد خرید شما:**\n\n"
    
    for item in cart:
        cart_id, product_name, pack_name, pack_qty, price, quantity = item
        item_total = price * quantity
        
        text += f"🏷 {product_name}\n"
        text += f"📦 {pack_name} ({quantity} پک)\n"
        text += f"💰 {item_total:,.0f} تومان\n\n"
    
    text += f"💵 جمع کل: {total_price:,.0f} تومان\n"
    text += f"🎁 تخفیف ({discount_code}): {discount_amount:,.0f} تومان\n"
    text += f"━━━━━━━━━━━━━━\n"
    text += f"💳 **مبلغ نهایی: {final_price:,.0f} تومان**"
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=cart_keyboard(cart)
    )
    
    return ConversationHandler.END


async def remove_applied_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف کد تخفیف اعمال شده"""
    context.user_data.pop('applied_discount_code', None)
    context.user_data.pop('discount_amount', None)
    context.user_data.pop('discount_id', None)
