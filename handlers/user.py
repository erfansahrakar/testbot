"""
هندلرهای مربوط به کاربران

"""
import json
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from message_customizer import message_customizer
from validators import Validators
from logger import log_user_action, log_order, log_discount_usage
from states import FULL_NAME, ADDRESS_TEXT, PHONE_NUMBER
from rate_limiter import rate_limit, action_limit
from keyboards import (
    user_main_keyboard,
    product_inline_keyboard,
    quantity_keyboard,
    cart_keyboard,
    view_cart_keyboard,
    cancel_keyboard
)

logger = logging.getLogger(__name__)

# ✅ Lock برای جلوگیری از Race Condition در cart operations
cart_locks = {}  # به ازای هر کاربر یک Lock


# ==================== HELPER FUNCTIONS ====================

async def _update_cart_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     cart_id: int, delta: int):
    """
    ✅ FIX باگ 1: Helper function برای تغییر تعداد
    این تابع Memory Leak نداره چون از transaction() استفاده میکنه
    ✅ FIX باگ 5: استفاده از Lock برای Race Condition
    
    Args:
        update: Update object
        context: Context object
        cart_id: شناسه آیتم در سبد
        delta: تغییر تعداد (+1 برای افزایش، -1 برای کاهش)
    
    Returns:
        tuple: (success: bool, new_quantity: int, message: str)
    """
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # ✅ اگه این کاربر قفل نداره، بساز
    if user_id not in cart_locks:
        cart_locks[user_id] = asyncio.Lock()
    
    # ✅ قفل کن تا کار قبلی تموم شه
    async with cart_locks[user_id]:
        try:
            # دریافت اطلاعات cart item
            conn = db._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.product_id, c.pack_id, c.quantity, 
                       pk.quantity as pack_qty, pk.name, p.name
                FROM cart c
                JOIN packs pk ON c.pack_id = pk.id
                JOIN products p ON c.product_id = p.id
                WHERE c.id = ? AND c.user_id = ?
            """, (cart_id, user_id))
            
            result = cursor.fetchone()
            
            if not result:
                return False, 0, "❌ آیتم یافت نشد!"
            
            cart_id_val, product_id, pack_id, current_qty, pack_qty, pack_name, product_name = result
            
            # محاسبه تعداد جدید
            new_qty = current_qty + (delta * pack_qty)
            
            # ✅ FIX: استفاده از Transaction برای جلوگیری از Memory Leak
            with db.transaction() as cursor:
                if new_qty <= 0:
                    # حذف آیتم
                    cursor.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
                    action = "حذف از سبد"
                    message = f"🗑 آیتم حذف شد!"
                else:
                    # بروزرسانی تعداد
                    cursor.execute("UPDATE cart SET quantity = ? WHERE id = ?", (new_qty, cart_id))
                    action = "افزایش در سبد" if delta > 0 else "کاهش در سبد"
                    change_text = "➕" if delta > 0 else "➖"
                    message = f"{change_text} {abs(delta * pack_qty)} عدد {'اضافه' if delta > 0 else 'کم'} شد!\n🔢 تعداد جدید: {new_qty} عدد"
            
            # Invalidate cache
            db._invalidate_cache(f"cart:{user_id}")
            
            # ثبت لاگ
            log_user_action(user_id, action, f"{product_name} - {pack_name}")
            
            return True, new_qty, message
            
        except Exception as e:
            logger.error(f"❌ خطا در _update_cart_item_quantity: {e}")
            return False, 0, "❌ خطا در بروزرسانی سبد!"


async def _refresh_cart_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    بروزرسانی نمایش سبد خرید
    ✅ FIX: حفظ تخفیف بعد از +/-
    
    Returns:
        bool: آیا سبد خالی است؟
    """
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    cart = db.get_cart(user_id)
    
    if not cart:
        await query.edit_message_text("✅ سبد خرید شما خالی شد.")
        # پاک کردن تخفیف اگه سبد خالی شد
        context.user_data.pop('applied_discount_code', None)
        context.user_data.pop('discount_amount', None)
        context.user_data.pop('discount_id', None)
        return True
    
    # محاسبه جمع کل
    total_price = 0
    for item in cart:
        cart_id_item, product_name, pack_name, pack_qty, pack_price, item_qty = item
        
        unit_price = pack_price / pack_qty
        item_total = unit_price * item_qty
        total_price += item_total
    
    # ✅ FIX: بررسی وجود تخفیف و محاسبه مجدد
    discount_code = context.user_data.get('applied_discount_code')
    discount_amount = 0
    
    if discount_code:
        discount = db.get_discount(discount_code)
        if discount:
            disc_type = discount[2]
            value = discount[3]
            min_purchase = discount[4]
            max_discount = discount[5]
            
            # بررسی اینکه هنوز واجد شرایط هست
            if total_price >= min_purchase:
                if disc_type == 'percentage':
                    discount_amount = total_price * (value / 100)
                    if max_discount and discount_amount > max_discount:
                        discount_amount = max_discount
                else:
                    discount_amount = value
                
                # بروزرسانی مقدار تخفیف
                context.user_data['discount_amount'] = discount_amount
            else:
                # مبلغ کمتر از حداقل شد - حذف تخفیف
                context.user_data.pop('applied_discount_code', None)
                context.user_data.pop('discount_amount', None)
                context.user_data.pop('discount_id', None)
                discount_code = None
    
    # ساخت متن سبد
    text = "🛒 سبد خرید شما:\n\n"
    
    for item in cart:
        cart_id_item, product_name, pack_name, pack_qty, pack_price, item_qty = item
        
        unit_price = pack_price / pack_qty
        item_total = unit_price * item_qty
        
        text += f"🏷 {product_name}\n"
        text += f"📦 {pack_name} ({item_qty} عدد)\n"
        text += f"💰 {item_total:,.0f} تومان\n\n"
    
    text += f"💵 جمع کل: {total_price:,.0f} تومان\n"
    
    # ✅ FIX: نمایش تخفیف اگه وجود داشت
    if discount_code and discount_amount > 0:
        final_price = total_price - discount_amount
        text += f"🎁 تخفیف ({discount_code}): {discount_amount:,.0f} تومان\n"
        text += f"━━━━━━━━━━━━━━\n"
        text += f"💳 **مبلغ نهایی: {final_price:,.0f} تومان**"
    else:
        text += f"💳 جمع کل: {total_price:,.0f} تومان"
    
    # بررسی موجودی کیف پول برای نمایش دکمه
    wallet_balance = 0
    wallet_info = db.get_wallet_balance(user_id)
    if wallet_info and wallet_info[0] > 0:
        wallet_balance = wallet_info[0]
    
    await query.edit_message_text(text, reply_markup=cart_keyboard(cart, wallet_balance, total_price), parse_mode='Markdown')
    return False


# ==================== USER START & PRODUCT DISPLAY ====================

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام خوش‌آمدگویی به کاربر"""
    user = update.effective_user
    db = context.bot_data['db']
    
    # ثبت کاربر در دیتابیس
    db.add_user(user.id, user.username, user.first_name)
    
    # بررسی اگر از لینک خاصی اومده
    if context.args:
        arg = context.args[0]
        
        # مشاهده سبد خرید
        if arg == 'view_cart':
            await view_cart(update, context)
            return
        
        # فرمت: product_X_pack_Y
        elif arg.startswith('product_') and '_pack_' in arg:
            parts = arg.split('_')
            product_id = int(parts[1])
            pack_id = int(parts[3])
            
            pack = db.get_pack(pack_id)
            product = db.get_product(product_id)
            
            if pack and product:
                _, _, pack_name, quantity, price = pack
                _, prod_name, *_ = product
                
                text = f"🏷 **{prod_name}**\n\n"
                text += f"📦 {pack_name}\n"
                text += f"💰 قیمت: {price:,.0f} تومان\n"
                text += f"🔢 هر بار کلیک = {quantity} عدد\n\n"
                text += "چند بار می‌خواهید اضافه کنید؟"
                
                await update.message.reply_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=quantity_keyboard(product_id, pack_id)
                )
                return
        
        # فرمت قدیمی: product_X
        elif arg.startswith('product_'):
            product_id = int(arg.split('_')[1])
            await show_product(update, context, product_id)
            return
    
    from config import get_start_message
    from message_customizer import message_customizer
    
    # دریافت اسم کاربر
    user_name = user.first_name if user.first_name else "کاربر"
    
    # دریافت پیام با اسم کاربر
    start_message = message_customizer.get_message("start_user", name=user_name)
    
    await update.message.reply_text(
        start_message,
        reply_markup=user_main_keyboard()
    )


async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    """نمایش محصول به کاربر"""
    db = context.bot_data['db']
    product = db.get_product(product_id)
    
    if not product:
        await update.message.reply_text("❌ محصول یافت نشد.")
        return
    
    prod_id, name, desc, photo_id, *_ = product
    packs = db.get_packs(product_id)
    
    if not packs:
        await update.message.reply_text("❌ این محصول فعلاً موجود نیست.")
        return
    
    text = f"🏷 {name}\n\n{desc}\n\n📦 انتخاب پک:"
    
    if photo_id:
        await update.message.reply_photo(
            photo_id,
            caption=text,
            reply_markup=product_inline_keyboard(product_id, packs)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=product_inline_keyboard(product_id, packs)
        )


# ==================== CART OPERATIONS ====================

@rate_limit(max_requests=20, window_seconds=60)
async def handle_pack_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    انتخاب پک - افزودن مستقیم به سبد
    ✅ FIX: استفاده از Lock
    """
    query = update.callback_query
    
    data = query.data.split(":")
    product_id = int(data[1])
    pack_id = int(data[2])
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # ✅ اگه این کاربر قفل نداره، بساز
    if user_id not in cart_locks:
        cart_locks[user_id] = asyncio.Lock()
    
    # ✅ قفل کن - صبر کن تا کار قبلی تموم شه
    async with cart_locks[user_id]:
        # ثبت کاربر اگه قبلاً ثبت نشده
        user = update.effective_user
        db.add_user(user.id, user.username, user.first_name)
        
        pack = db.get_pack(pack_id)
        product = db.get_product(product_id)
        
        if not pack or not product:
            await query.answer("❌ محصول یافت نشد!", show_alert=True)
            return
        
        _, _, pack_name, pack_qty, price = pack
        _, prod_name, *_ = product
        
        # افزودن 1 بار کلیک = pack_qty عدد
        try:
            db.add_to_cart(user_id, product_id, pack_id, quantity=1)
            log_user_action(user_id, "افزودن به سبد", f"{prod_name} - {pack_name}")
        except Exception as e:
            logger.error(f"❌ خطا در افزودن به سبد: {e}")
            await query.answer("❌ خطا در افزودن به سبد!", show_alert=True)
            return
        
        # محاسبه تعداد کل در سبد
        cart = db.get_cart(user_id)
        total_this_pack_count = 0
        total_price_this_pack = 0
        total_items = 0
        total_price_all = 0
        
        for item in cart:
            cart_id, p_name, pk_name, pk_qty, pk_price, item_qty = item
            
            if pk_name == pack_name and p_name == prod_name:
                total_this_pack_count += item_qty
                unit_price = pk_price / pk_qty
                total_price_this_pack += unit_price * item_qty
            
            total_items += item_qty
            unit_price = pk_price / pk_qty
            total_price_all += unit_price * item_qty
        
        # نمایش Alert
        alert_text = f"✅ {pack_qty} عدد اضافه شد!\n\n"
        alert_text += f"📦 {pack_name}\n"
        alert_text += f"🔢 تعداد در سبد: {total_this_pack_count} عدد\n"
        alert_text += f"💰 {total_price_this_pack:,.0f} تومان\n\n"
        alert_text += f"📊 کل کالاها در سبد: {total_items} عدد\n"
        alert_text += f"💳 جمع کل: {total_price_all:,.0f} تومان\n\n"
        alert_text += f"✅ درصورت تمام شدن روی سبد خرید کلیک کنید"
        
        await query.answer(alert_text, show_alert=True)


async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش سبد خرید"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    cart = db.get_cart(user_id)
    
    if not cart:
        message = "🛒 سبد خرید شما خالی است!"
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    text = "🛒 سبد خرید شما:\n\n"
    total_price = 0
    
    for item in cart:
        cart_id, product_name, pack_name, pack_qty, pack_price, item_qty = item
        
        unit_price = pack_price / pack_qty
        item_total = unit_price * item_qty
        total_price += item_total
        
        text += f"🏷 {product_name}\n"
        text += f"📦 {pack_name} ({item_qty} عدد)\n"
        text += f"💰 {item_total:,.0f} تومان\n\n"
    
    text += f"💳 جمع کل: {total_price:,.0f} تومان"
    
    # بررسی موجودی کیف پول برای نمایش دکمه
    wallet_balance = 0
    wallet_info = db.get_wallet_balance(user_id)
    if wallet_info and wallet_info[0] > 0:
        wallet_balance = wallet_info[0]
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            text,
            reply_markup=cart_keyboard(cart, wallet_balance, total_price)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=cart_keyboard(cart, wallet_balance, total_price)
        )


async def cart_increase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ REFACTORED: افزایش تعداد در سبد خرید
    استفاده از helper function برای حذف تکرار کد
    ✅ Lock به صورت خودکار در helper function اعمال میشه
    """
    query = update.callback_query
    cart_id = int(query.data.split(":")[1])
    
    # استفاده از helper function (که خودش Lock داره)
    success, new_qty, message = await _update_cart_item_quantity(update, context, cart_id, delta=+1)
    
    if not success:
        await query.answer(message, show_alert=True)
        return
    
    # نمایش پیام موفقیت
    await query.answer(message, show_alert=True)
    
    # بروزرسانی نمایش سبد
    await _refresh_cart_display(update, context)


async def cart_decrease(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ REFACTORED: کاهش تعداد در سبد خرید
    استفاده از helper function برای حذف تکرار کد
    ✅ Lock به صورت خودکار در helper function اعمال میشه
    """
    query = update.callback_query
    cart_id = int(query.data.split(":")[1])
    
    # استفاده از helper function (که خودش Lock داره)
    success, new_qty, message = await _update_cart_item_quantity(update, context, cart_id, delta=-1)
    
    if not success:
        await query.answer(message, show_alert=True)
        return
    
    # نمایش پیام موفقیت
    await query.answer(message, show_alert=True)
    
    # بروزرسانی نمایش سبد
    await _refresh_cart_display(update, context)


async def remove_from_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    حذف از سبد خرید
    ✅ FIX: استفاده از Lock
    """
    query = update.callback_query
    await query.answer("🗑 حذف شد!")
    
    cart_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # ✅ اگه این کاربر قفل نداره، بساز
    if user_id not in cart_locks:
        cart_locks[user_id] = asyncio.Lock()
    
    # ✅ قفل کن
    async with cart_locks[user_id]:
        try:
            db.remove_from_cart(cart_id)
        except Exception as e:
            logger.error(f"❌ خطا در حذف از سبد: {e}")
            await query.answer("❌ خطا در حذف آیتم!", show_alert=True)
            return
        
        # بروزرسانی نمایش سبد
        await _refresh_cart_display(update, context)


async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    خالی کردن سبد خرید
    ✅ FIX: استفاده از Lock
    """
    query = update.callback_query
    await query.answer("🗑 سبد خرید خالی شد!")
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # ✅ اگه این کاربر قفل نداره، بساز
    if user_id not in cart_locks:
        cart_locks[user_id] = asyncio.Lock()
    
    # ✅ قفل کن
    async with cart_locks[user_id]:
        try:
            db.clear_cart(user_id)
        except Exception as e:
            logger.error(f"❌ خطا در خالی کردن سبد: {e}")
            await query.answer("❌ خطا در خالی کردن سبد!", show_alert=True)
            return
        
        await query.message.edit_text("✅ سبد خرید شما خالی شد.")


# ==================== ORDER FINALIZATION ====================

@action_limit('order', max_requests=3, window_seconds=3600)
async def finalize_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع نهایی کردن سفارش"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    user = db.get_user(user_id)
    
    # بررسی اطلاعات کاربر
    has_full_info = (
        user[3] and  # full_name
        user[4] and  # phone
        len(user) > 6 and user[6]  # address
    )
    
    if not has_full_info:
        await query.message.reply_text(
            "📝 لطفاً **نام و نام خانوادگی** خود را وارد کنید:",
            parse_mode='Markdown',
            reply_markup=cancel_keyboard()
        )
        return FULL_NAME
    else:
        from keyboards import confirm_info_keyboard
        
        info_text = "📋 **مشخصات شما:**\n\n"
        info_text += f"👤 نام: {user[3]}\n"
        info_text += f"📱 موبایل: {user[4]}\n"
        if user[5]:
            info_text += f"☎️ ثابت: {user[5]}\n"
        info_text += f"📍 آدرس: {user[6]}\n"
        if len(user) > 7 and user[7]:
            info_text += f"🏪 فروشگاه: {user[7]}\n"
        
        info_text += "\n❓ **آیا اطلاعات صحیح است؟**"
        
        await query.message.reply_text(
            info_text,
            parse_mode='Markdown',
            reply_markup=confirm_info_keyboard()
        )
        return ConversationHandler.END


# ==================== USER INFO COLLECTION ====================

async def full_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام و نام خانوادگی - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=user_main_keyboard())
        return ConversationHandler.END
    
    full_name = update.message.text
    
    is_valid, error_msg, cleaned_name = Validators.validate_name(full_name)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return FULL_NAME
    
    context.user_data['temp_full_name'] = cleaned_name
    
    await update.message.reply_text(
        "📍 لطفاً **آدرس دقیق** خود را وارد کنید:\n\n"
        "مثال: تهران، خیابان ولیعصر، کوچه ۱۵، پلاک ۲۳",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    return ADDRESS_TEXT


async def address_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت آدرس - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=user_main_keyboard())
        return ConversationHandler.END
    
    address = update.message.text
    
    is_valid, error_msg, cleaned_address = Validators.validate_address(address)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return ADDRESS_TEXT
    
    context.user_data['temp_address'] = cleaned_address
    
    await update.message.reply_text(
        "📱 لطفاً **شماره تماس** خود را وارد کنید:\n\n"
        "مثال: 09123456789",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    return PHONE_NUMBER


async def phone_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت شماره تماس و ذخیره نهایی - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=user_main_keyboard())
        return ConversationHandler.END
    
    phone = update.message.text
    
    is_valid, error_msg = Validators.validate_phone(phone)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return PHONE_NUMBER
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    full_name = context.user_data.get('temp_full_name', '')
    address = context.user_data.get('temp_address', '')
    
    db.update_user_info(
        user_id, 
        phone=phone, 
        address=address, 
        full_name=full_name
    )
    
    context.user_data.pop('temp_full_name', None)
    context.user_data.pop('temp_address', None)
    
    is_editing_address = context.user_data.get('editing_address', False)
    is_editing_for_order = context.user_data.get('editing_for_order', False)
    
    if is_editing_address and not is_editing_for_order:
        context.user_data.pop('editing_address', None)
        await update.message.reply_text(
            "✅ آدرس شما با موفقیت بروزرسانی شد!",
            reply_markup=user_main_keyboard()
        )
        return ConversationHandler.END
    
    if is_editing_for_order:
        context.user_data.pop('editing_for_order', None)
        context.user_data.pop('editing_address', None)
        
        await update.message.reply_text("✅ مشخصات شما ویرایش شد!")
        
        # ✅ FIX: بعد از ویرایش اطلاعات، فاکتور نهایی دوباره نشون بده
        order_id = context.user_data.get('confirming_order')
        if order_id:
            # سفارش قبلاً وجود داشت (مثلاً از فاکتور نهایی ویرایش زده شده بود)
            await show_final_invoice(update, context, order_id)
        else:
            # سفارش هنوز ثبت نشده — باید اول سفارش ثبت بشه، بعد فاکتور نشون بده
            # اطلاعات کاربر رو تایید کن و بذار فلوء نرمال ادامه پیدا کنه
            from keyboards import confirm_info_keyboard
            
            info_text = "📋 **مشخصات جدید شما:**\n\n"
            info_text += f"👤 نام: {full_name}\n"
            info_text += f"📱 موبایل: {phone}\n"
            info_text += f"📍 آدرس: {address}\n"
            info_text += "\n❓ **آیا اطلاعات صحیح است؟**"
            
            await update.message.reply_text(
                info_text,
                parse_mode='Markdown',
                reply_markup=confirm_info_keyboard()
            )
        
        return ConversationHandler.END
    
    await create_order_from_message(update, context)
    return ConversationHandler.END


async def confirm_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید اطلاعات قبلی کاربر یا جدید کاربر"""
    query = update.callback_query
    await query.answer("✅ اطلاعات تایید شد")
    
    # ✅ FIX: اگه سفارش قبلاً وجود داشت (مثلاً از فاکتور نهایی ویرایش زده شده بود)
    # فاکتور نهایی دوباره نشون بده
    order_id = context.user_data.get('confirming_order')
    if order_id:
        await show_final_invoice(update, context, order_id)
    else:
        # سفارش جدیده — سفارش ثبت کن
        await create_order(update, context)


async def edit_user_info_for_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ویرایش اطلاعات برای سفارش"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "📝 لطفاً **نام و نام خانوادگی** خود را وارد کنید:",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    context.user_data['editing_for_order'] = True
    return FULL_NAME


async def use_old_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استفاده از آدرس قبلی"""
    query = update.callback_query
    await query.answer("✅ از آدرس قبلی استفاده می‌شود")
    
    await create_order(update, context)


async def use_new_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وارد کردن آدرس جدید"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "📝 لطفاً **نام و نام خانوادگی** خود را وارد کنید:",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    context.user_data['from_finalize'] = True
    return FULL_NAME


# ==================== ORDER CREATION ====================

async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ FIXED باگ 4: ایجاد سفارش با Transaction
    تمام عملیات داخل یک transaction هستن
    ✅ FIXED باگ 5: استفاده از Lock برای Race Condition
    """
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # ✅ اگه این کاربر قفل نداره، بساز
    if user_id not in cart_locks:
        cart_locks[user_id] = asyncio.Lock()
    
    # ✅ قفل کن - این خیلی مهمه چون cart رو خالی میکنیم
    async with cart_locks[user_id]:
        cart = db.get_cart(user_id)
        if not cart:
            await query.message.reply_text("سبد خرید شما خالی است!")
            return
        
        # آماده‌سازی آیتم‌های سفارش
        items = []
        total_price = 0
        
        for item in cart:
            cart_id, product_name, pack_name, pack_qty, pack_price, item_qty = item
            
            unit_price = pack_price / pack_qty
            item_total = unit_price * item_qty
            total_price += item_total
            
            items.append({
                'product': product_name,
                'pack': pack_name,
                'pack_quantity': pack_qty,
                'unit_price': unit_price,
                'quantity': item_qty,
                'price': item_total,
                'pack_price': pack_price
            })
        
        discount_code = context.user_data.get('applied_discount_code')
        discount_amount = context.user_data.get('discount_amount', 0)
        final_price = total_price - discount_amount
        
        try:
            # ✅ FIX: استفاده از Transaction برای atomicity
            with db.transaction() as cursor:
                # 1. ثبت سفارش
                cursor.execute("""
                    INSERT INTO orders 
                    (user_id, items, total_price, discount_amount, final_price, discount_code, expires_at) 
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+1 day'))
                """, (user_id, json.dumps(items, ensure_ascii=False), total_price, 
                      discount_amount, final_price, discount_code))
                order_id = cursor.lastrowid
                
                # 2. ثبت استفاده از تخفیف (اگر وجود داشت)
                if discount_code:
                    cursor.execute("""
                        INSERT INTO discount_usage (user_id, discount_code, order_id) 
                        VALUES (?, ?, ?)
                    """, (user_id, discount_code, order_id))
                    
                    cursor.execute("""
                        UPDATE discount_codes 
                        SET used_count = used_count + 1 
                        WHERE code = ?
                    """, (discount_code,))
                
                # 3. خالی کردن سبد خرید
                cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
            
            # ✅ Transaction موفق بود - حالا می‌تونیم log کنیم
            log_order(order_id, user_id, "pending", final_price)
            
            if discount_code:
                log_discount_usage(user_id, discount_code, discount_amount)
            
            # پاکسازی context
            context.user_data.pop('applied_discount_code', None)
            context.user_data.pop('discount_amount', None)
            context.user_data.pop('discount_id', None)
            
            # Invalidate cache
            db._invalidate_cache(f"cart:{user_id}")
            db._invalidate_cache("stats:")
            
            # نمایش پیام موفقیت
            await query.message.reply_text(
                message_customizer.get_message("order_received"),
                reply_markup=user_main_keyboard()
            )
            
            logger.info(f"✅ سفارش {order_id} با موفقیت ثبت شد")
            
        except Exception as e:
            # ✅ Transaction خودکار rollback شده
            logger.error(f"❌ خطا در ثبت سفارش: {e}")
            await query.message.reply_text(
                "❌ خطا در ثبت سفارش! لطفاً دوباره تلاش کنید.",
                reply_markup=user_main_keyboard()
            )
            return
        
        # ✅ FIX: send_order_to_admin جداگانه - اگه خطا بده سفارش خراب نشه
        try:
            from handlers.order import send_order_to_admin
            await send_order_to_admin(context, order_id)
        except Exception as e:
            logger.error(f"❌ خطا در ارسال سفارش به ادمین: {e}")


async def create_order_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ FIXED باگ 4: ایجاد سفارش از پیام با Transaction
    ✅ FIXED باگ 5: استفاده از Lock برای Race Condition
    """
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    # ✅ اگه این کاربر قفل نداره، بساز
    if user_id not in cart_locks:
        cart_locks[user_id] = asyncio.Lock()
    
    # ✅ قفل کن
    async with cart_locks[user_id]:
        cart = db.get_cart(user_id)
        if not cart:
            await update.message.reply_text("سبد خرید شما خالی است!")
            return
        
        # آماده‌سازی آیتم‌های سفارش
        items = []
        total_price = 0
        
        for item in cart:
            cart_id, product_name, pack_name, pack_qty, pack_price, item_qty = item
            
            unit_price = pack_price / pack_qty
            item_total = unit_price * item_qty
            total_price += item_total
            
            items.append({
                'product': product_name,
                'pack': pack_name,
                'pack_quantity': pack_qty,
                'unit_price': unit_price,
                'quantity': item_qty,
                'price': item_total,
                'pack_price': pack_price
            })
        
        discount_code = context.user_data.get('applied_discount_code')
        discount_amount = context.user_data.get('discount_amount', 0)
        final_price = total_price - discount_amount
        
        try:
            # ✅ FIX: استفاده از Transaction
            with db.transaction() as cursor:
                # 1. ثبت سفارش
                cursor.execute("""
                    INSERT INTO orders 
                    (user_id, items, total_price, discount_amount, final_price, discount_code, expires_at) 
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+1 day'))
                """, (user_id, json.dumps(items, ensure_ascii=False), total_price, 
                      discount_amount, final_price, discount_code))
                order_id = cursor.lastrowid
                
                # 2. ثبت استفاده از تخفیف
                if discount_code:
                    cursor.execute("""
                        INSERT INTO discount_usage (user_id, discount_code, order_id) 
                        VALUES (?, ?, ?)
                    """, (user_id, discount_code, order_id))
                    
                    cursor.execute("""
                        UPDATE discount_codes 
                        SET used_count = used_count + 1 
                        WHERE code = ?
                    """, (discount_code,))
                
                # 3. خالی کردن سبد
                cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
            
            # Transaction موفق - ثبت log
            log_order(order_id, user_id, "pending", final_price)
            
            if discount_code:
                log_discount_usage(user_id, discount_code, discount_amount)
            
            # پاکسازی
            context.user_data.pop('applied_discount_code', None)
            context.user_data.pop('discount_amount', None)
            context.user_data.pop('discount_id', None)
            
            db._invalidate_cache(f"cart:{user_id}")
            db._invalidate_cache("stats:")
            
            await update.message.reply_text(
                message_customizer.get_message("order_received"),
                reply_markup=user_main_keyboard()
            )
            
            logger.info(f"✅ سفارش {order_id} با موفقیت ثبت شد")
            
        except Exception as e:
            logger.error(f"❌ خطا در ثبت سفارش: {e}")
            await update.message.reply_text(
                "❌ خطا در ثبت سفارش! لطفاً دوباره تلاش کنید.",
                reply_markup=user_main_keyboard()
            )
            return
        
        # ✅ FIX: send_order_to_admin جداگانه - اگه خطا بده سفارش خراب نشه
        try:
            from handlers.order import send_order_to_admin
            await send_order_to_admin(context, order_id)
        except Exception as e:
            logger.error(f"❌ خطا در ارسال سفارش به ادمین: {e}")


# ==================== SHIPPING & INVOICE ====================

async def back_to_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به انتخاب پک"""
    query = update.callback_query
    await query.answer("دکمه‌های پک همیشه نمایش داده می‌شوند!", show_alert=True)


async def handle_shipping_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب نحوه ارسال"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    order_id = context.bot_data.get(f'pending_shipping_{user_id}')
    
    if not order_id:
        await query.message.reply_text("❌ خطا! لطفاً دوباره تلاش کنید.")
        return
    
    shipping_map = {
        "ship_terminal": "ترمینال 🚌",
        "ship_barbari": "باربری 🚚",
        "ship_tipax": "تیپاکس 📦",
        "ship_chapar": "چاپار 🏃"
    }
    
    shipping_method = shipping_map.get(query.data, "نامشخص")
    db.update_shipping_method(order_id, shipping_method)
    
    await show_final_invoice(update, context, order_id)


def _html_escape(text):
    """Escape کاراکترهای خاص HTML تا متن داده کاربر خراب نشه"""
    if not text:
        return text
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


async def show_final_invoice(update, context, order_id):
    """نمایش فاکتور نهایی - با HTML به جای Markdown"""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    if not order:
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *_ = order
    items = json.loads(items_json)
    user = db.get_user(user_id)

    # ==================== نمایش موجودی کیف پول (بدون کسر خودکار) ====================
    wallet_info_text = ""
    wallet_balance = 0
    from datetime import datetime as _dt
    wallet_info = db.get_wallet_balance(user_id)
    if wallet_info and wallet_info[0] > 0:
        expires_at_w = wallet_info[1]
        wallet_valid = True
        if expires_at_w:
            exp = _dt.fromisoformat(expires_at_w) if isinstance(expires_at_w, str) else expires_at_w
            if exp.tzinfo is None:
                from database import TEHRAN_TZ
                exp = TEHRAN_TZ.localize(exp)
            from database import get_tehran_now
            wallet_valid = get_tehran_now() < exp
        if wallet_valid:
            wallet_balance = wallet_info[0]
            usable = min(wallet_balance, final_price)
            wallet_info_text = f"\n💰 <b>موجودی کیف پول شما:</b> {wallet_balance:,.0f} تومان (حداکثر {usable:,.0f} تومان قابل استفاده)\n"
    # =============================================================

    invoice_text = "📋 <b>فاکتور نهایی سفارش</b>\n"
    invoice_text += "═" * 25 + "\n\n"
    
    invoice_text += "🛍 <b>محصولات:</b>\n"
    for item in items:
        invoice_text += f"▫️ {_html_escape(item['product'])} - {_html_escape(item['pack'])}\n"
        invoice_text += f"   تعداد: {item['quantity']} عدد\n"
        invoice_text += f"   قیمت: {item['price']:,.0f} تومان\n\n"
    
    invoice_text += f"💰 <b>جمع کل:</b> {total_price:,.0f} تومان\n"
    
    if discount_amount > 0:
        invoice_text += f"🎁 <b>تخفیف:</b> {discount_amount:,.0f} تومان\n"
        if discount_code:
            invoice_text += f"🎫 <b>کد تخفیف:</b> {_html_escape(discount_code)}\n"

    if wallet_info_text:
        invoice_text += wallet_info_text

    invoice_text += f"💳 <b>مبلغ قابل پرداخت:</b> {final_price:,.0f} تومان\n"

    invoice_text += "═" * 25 + "\n\n"
    
    invoice_text += "👤 <b>مشخصات گیرنده:</b>\n"
    if user[3]:
        invoice_text += f"▫️ نام: {_html_escape(user[3])}\n"
    if user[4]:
        invoice_text += f"▫️ موبایل: {_html_escape(user[4])}\n"
    if user[5]:
        invoice_text += f"▫️ ثابت: {_html_escape(user[5])}\n"
    if len(user) > 6 and user[6]:
        invoice_text += f"▫️ آدرس: {_html_escape(user[6])}\n"
    if len(user) > 7 and user[7]:
        invoice_text += f"▫️ فروشگاه: {_html_escape(user[7])}\n"
    
    invoice_text += "\n"
    
    if shipping_method:
        invoice_text += f"📦 <b>نحوه ارسال:</b> {_html_escape(shipping_method)}\n\n"
    
    invoice_text += "═" * 25 + "\n\n"
    invoice_text += "❓ <b>آیا همه اطلاعات مورد تایید است؟</b>"

    from keyboards import final_confirmation_keyboard_with_wallet
    context.user_data['confirming_order'] = order_id
    
    keyboard = final_confirmation_keyboard_with_wallet(order_id, wallet_balance, final_price)
    
    if query:
        await query.message.reply_text(
            invoice_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    else:
        await context.bot.send_message(
            user_id,
            invoice_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )


async def final_confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید نهایی سفارش"""
    query = update.callback_query
    await query.answer("✅ سفارش شما ثبت شد!")
    
    order_id = context.user_data.get('confirming_order')
    
    if not order_id:
        await query.message.reply_text("❌ خطا! لطفاً دوباره تلاش کنید.")
        return

    db = context.bot_data['db']
    user_id = update.effective_user.id

    # ==================== کسر کیف پول (اگه کاربر انتخاب کرده بود) ====================
    # هم از سبد خرید و هم از فاکتور بررسی می‌کنیم
    wallet_deducted = context.user_data.pop('wallet_use_for_order', None)
    wallet_cart = context.user_data.pop('wallet_use_in_cart', None)
    if not wallet_deducted and wallet_cart:
        wallet_deducted = {'order_id': order_id, 'amount': wallet_cart['amount']}
    wallet_msg = ""
    if wallet_deducted and wallet_deducted.get('order_id') == order_id:
        usable = wallet_deducted['amount']
        success = db.deduct_wallet(
            user_id=user_id,
            amount=usable,
            description=f"پرداخت سفارش #{order_id}",
            order_id=order_id
        )
        if success:
            order = db.get_order(order_id)
            final_price = order[5]
            new_final = final_price - usable
            db.update_order_wallet_payment(order_id, usable, new_final)
            wallet_msg = f"\n💰 {usable:,.0f} تومان از کیف پول کسر شد."
    # =================================================================================

    db.update_order_status(order_id, 'confirmed')
    
    context.bot_data.pop(f'pending_shipping_{user_id}', None)
    context.user_data.pop('confirming_order', None)
    context.user_data.pop('wallet_balance_for_order', None)
    
    await query.message.reply_text(
        "✅ **سفارش شما ثبت نهایی شد!**\n\n"
        "📦 سفارش شما به‌زودی ارسال خواهد شد.\n\n"
        "🙏 از خرید شما سپاسگزاریم!" + wallet_msg,
        parse_mode='Markdown',
        reply_markup=user_main_keyboard()
    )
    
    from config import ADMIN_ID
    await context.bot.send_message(
        ADMIN_ID,
        f"✅ سفارش #{order_id} توسط کاربر تایید نهایی شد و آماده ارسال است."
    )


async def use_wallet_in_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استفاده از کیف پول در فاکتور (انتخابی توسط کاربر)"""
    query = update.callback_query

    data = query.data.split(":")
    order_id = int(data[1])
    user_id = query.from_user.id
    db = context.bot_data['db']

    order = db.get_order(order_id)
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return

    final_price = order[5]

    wallet_info = db.get_wallet_balance(user_id)
    if not wallet_info or wallet_info[0] <= 0:
        await query.answer("❌ موجودی کیف پول شما کافی نیست!", show_alert=True)
        return

    from datetime import datetime as _dt
    expires_at_w = wallet_info[1]
    wallet_valid = True
    if expires_at_w:
        exp = _dt.fromisoformat(expires_at_w) if isinstance(expires_at_w, str) else expires_at_w
        if exp.tzinfo is None:
            from database import TEHRAN_TZ
            exp = TEHRAN_TZ.localize(exp)
        from database import get_tehran_now
        wallet_valid = get_tehran_now() < exp

    if not wallet_valid:
        await query.answer("⚠️ اعتبار کیف پول شما منقضی شده است!", show_alert=True)
        return

    wallet_balance = wallet_info[0]
    usable = min(wallet_balance, final_price)

    # ذخیره در user_data برای استفاده موقع تأیید نهایی
    context.user_data['wallet_use_for_order'] = {'order_id': order_id, 'amount': usable}

    await query.answer(f"✅ {usable:,.0f} تومان از کیف پول موقع تأیید نهایی کسر می‌شود!", show_alert=True)

    # نمایش مجدد فاکتور با مبلغ بعد از کسر
    new_final = final_price - usable
    text = query.message.text or query.message.caption or ""

    # آپدیت متن فاکتور برای نمایش مبلغ جدید
    try:
        new_text = text
        import re
        new_text = re.sub(
            r'💳 <b>مبلغ قابل پرداخت:</b> [\d٬,]+ تومان',
            f'💰 <b>کسر از کیف پول:</b> -{usable:,.0f} تومان\n💳 <b>مبلغ قابل پرداخت:</b> {new_final:,.0f} تومان',
            new_text
        )
        from keyboards import final_confirmation_keyboard
        await query.message.edit_text(
            new_text,
            parse_mode='HTML',
            reply_markup=final_confirmation_keyboard()
        )
    except Exception:
        pass


async def use_wallet_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استفاده از کیف پول از طریق سبد خرید (قبل از نهایی کردن)"""
    query = update.callback_query
    # query.answer() را اینجا نمی‌زنیم - آخر تابع با پیام می‌زنیم

    user_id = query.from_user.id
    db = context.bot_data['db']

    wallet_info = db.get_wallet_balance(user_id)
    if not wallet_info or wallet_info[0] <= 0:
        await query.answer("❌ موجودی کیف پول شما کافی نیست!", show_alert=True)
        return

    from datetime import datetime as _dt
    expires_at_w = wallet_info[1]
    wallet_valid = True
    if expires_at_w:
        exp = _dt.fromisoformat(expires_at_w) if isinstance(expires_at_w, str) else expires_at_w
        if exp.tzinfo is None:
            from database import TEHRAN_TZ
            exp = TEHRAN_TZ.localize(exp)
        from database import get_tehran_now
        wallet_valid = get_tehran_now() < exp

    if not wallet_valid:
        await query.answer("⚠️ اعتبار کیف پول شما منقضی شده است!", show_alert=True)
        return

    wallet_balance = wallet_info[0]

    # محاسبه جمع کل سبد برای تعیین مقدار قابل استفاده
    cart = db.get_cart(user_id)
    total_price = 0
    if cart:
        for item in cart:
            _, _, _, pack_qty, pack_price, item_qty = item
            unit_price = pack_price / pack_qty
            total_price += unit_price * item_qty

    usable = min(wallet_balance, total_price) if total_price > 0 else wallet_balance

    # ذخیره در user_data برای استفاده موقع نهایی‌سازی سفارش
    context.user_data['wallet_use_in_cart'] = {'amount': usable}

    await query.answer(f"✅ {usable:,.0f} تومان از کیف پول موقع ثبت سفارش کسر می‌شود!", show_alert=True)


async def final_edit_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ویرایش اطلاعات سفارش"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "📝 لطفاً **نام و نام خانوادگی** خود را وارد کنید:",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    context.user_data['editing_for_order'] = True
    return FULL_NAME


# ==================== ADDRESS MANAGEMENT ====================

async def view_my_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آدرس ثبت شده"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ خطا! لطفاً /start کنید.")
        return
    
    full_name = user[3] if len(user) > 3 and user[3] else None
    phone = user[4] if len(user) > 4 and user[4] else None
    landline = user[5] if len(user) > 5 and user[5] else None
    address = user[6] if len(user) > 6 and user[6] else None
    shop_name = user[7] if len(user) > 7 and user[7] else None
    
    if not address or not phone or not full_name:
        from keyboards import edit_address_keyboard
        await update.message.reply_text(
            "📍 هنوز آدرسی ثبت نکرده‌اید!\n\n"
            "برای افزودن آدرس روی دکمه زیر کلیک کنید:",
            reply_markup=edit_address_keyboard()
        )
    else:
        from keyboards import edit_address_keyboard
        
        text = "📍 **آدرس ثبت شده شما:**\n\n"
        text += f"👤 نام: {full_name}\n"
        text += f"📱 موبایل: {phone}\n"
        if landline:
            text += f"☎️ ثابت: {landline}\n"
        text += f"📍 آدرس: {address}\n"
        if shop_name:
            text += f"🏪 فروشگاه: {shop_name}\n"
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=edit_address_keyboard()
        )


async def edit_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش آدرس"""
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        "📝 لطفاً **نام و نام خانوادگی** خود را وارد کنید:",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    context.user_data['editing_address'] = True
    return FULL_NAME


async def contact_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش اطلاعات تماس"""
    from config import format_contact_info
    
    text = format_contact_info()
    await update.message.reply_text(text, parse_mode='HTML')
