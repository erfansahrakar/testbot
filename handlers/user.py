"""
هندلرهای مربوط به کاربران
✅ FIX: ترتیب صحیح log_order و log_discount_usage
✅ حذف view_my_orders (جابجا شده به order.py)
"""
import json
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import MESSAGES
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
    
    await update.message.reply_text(
        MESSAGES["start_user"],
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


@rate_limit(max_requests=20, window_seconds=60)
async def handle_pack_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب پک - افزودن مستقیم به سبد"""
    query = update.callback_query
    
    data = query.data.split(":")
    product_id = int(data[1])
    pack_id = int(data[2])
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
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
    db.add_to_cart(user_id, product_id, pack_id, quantity=1)

    log_user_action(user_id, "افزودن به سبد", f"{prod_name} - {pack_name}")
    
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
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            text,
            reply_markup=cart_keyboard(cart)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=cart_keyboard(cart)
        )


async def remove_from_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف از سبد خرید"""
    query = update.callback_query
    await query.answer("🗑 حذف شد!")
    
    cart_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    db.remove_from_cart(cart_id)
    
    await view_cart(update, context)
    await query.message.delete()


async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خالی کردن سبد خرید"""
    query = update.callback_query
    await query.answer("🗑 سبد خرید خالی شد!")
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    db.clear_cart(user_id)
    
    await query.message.edit_text("✅ سبد خرید شما خالی شد.")


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
        
        await update.message.reply_text(
            "✅ مشخصات شما ویرایش شد!",
            reply_markup=user_main_keyboard()
        )
        
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
    """تایید اطلاعات قبلی کاربر"""
    query = update.callback_query
    await query.answer("✅ اطلاعات تایید شد")
    
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


async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ایجاد سفارش با unit_price"""
    query = update.callback_query
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    cart = db.get_cart(user_id)
    if not cart:
        await query.message.reply_text("سبد خرید شما خالی است!")
        return
    
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
    
    # ✅ اول ثبت سفارش
    order_id = db.create_order(
        user_id, 
        items, 
        total_price,
        discount_amount=discount_amount,
        final_price=final_price,
        discount_code=discount_code
    )
    
    # ✅ بعد لاگ سفارش
    log_order(order_id, user_id, "pending", final_price)
    
    if discount_code:
        discount_id = context.user_data.get('discount_id')
        db.use_discount(user_id, discount_code, order_id)
        
        # ✅ بعد لاگ تخفیف
        log_discount_usage(user_id, discount_code, discount_amount)
        
        context.user_data.pop('applied_discount_code', None)
        context.user_data.pop('discount_amount', None)
        context.user_data.pop('discount_id', None)
    
    db.clear_cart(user_id)
    
    await query.message.reply_text(
        MESSAGES["order_received"],
        reply_markup=user_main_keyboard()
    )
    
    from handlers.order import send_order_to_admin
    await send_order_to_admin(context, order_id)


async def create_order_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ایجاد سفارش از پیام با unit_price"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    cart = db.get_cart(user_id)
    if not cart:
        await update.message.reply_text("سبد خرید شما خالی است!")
        return
    
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
    
    # ✅ اول ثبت سفارش
    order_id = db.create_order(
        user_id, 
        items, 
        total_price,
        discount_amount=discount_amount,
        final_price=final_price,
        discount_code=discount_code
    )
    
    # ✅ بعد لاگ سفارش
    log_order(order_id, user_id, "pending", final_price)
    
    if discount_code:
        discount_id = context.user_data.get('discount_id')
        db.use_discount(user_id, discount_code, order_id)
        
        # ✅ بعد لاگ تخفیف
        log_discount_usage(user_id, discount_code, discount_amount)
        
        context.user_data.pop('applied_discount_code', None)
        context.user_data.pop('discount_amount', None)
        context.user_data.pop('discount_id', None)
    
    db.clear_cart(user_id)
    
    await update.message.reply_text(
        MESSAGES["order_received"],
        reply_markup=user_main_keyboard()
    )
    
    from handlers.order import send_order_to_admin
    await send_order_to_admin(context, order_id)


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


async def show_final_invoice(update, context, order_id):
    """نمایش فاکتور نهایی"""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    db = context.bot_data['db']
    
    order = db.get_order(order_id)
    if not order:
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    invoice_text = "📋 **فاکتور نهایی سفارش**\n"
    invoice_text += "═" * 25 + "\n\n"
    
    invoice_text += "🛍 **محصولات:**\n"
    for item in items:
        invoice_text += f"▫️ {item['product']} - {item['pack']}\n"
        invoice_text += f"   تعداد: {item['quantity']} عدد\n"
        invoice_text += f"   قیمت: {item['price']:,.0f} تومان\n\n"
    
    invoice_text += f"💰 **جمع کل:** {total_price:,.0f} تومان\n"
    
    if discount_amount > 0:
        invoice_text += f"🎁 **تخفیف:** {discount_amount:,.0f} تومان\n"
        if discount_code:
            invoice_text += f"🎫 **کد تخفیف:** {discount_code}\n"
        invoice_text += f"💳 **مبلغ نهایی:** {final_price:,.0f} تومان\n"
    
    invoice_text += "═" * 25 + "\n\n"
    
    invoice_text += "👤 **مشخصات گیرنده:**\n"
    if user[3]:
        invoice_text += f"▫️ نام: {user[3]}\n"
    if user[4]:
        invoice_text += f"▫️ موبایل: {user[4]}\n"
    if user[5]:
        invoice_text += f"▫️ ثابت: {user[5]}\n"
    if len(user) > 6 and user[6]:
        invoice_text += f"▫️ آدرس: {user[6]}\n"
    if len(user) > 7 and user[7]:
        invoice_text += f"▫️ فروشگاه: {user[7]}\n"
    
    invoice_text += "\n"
    
    if shipping_method:
        invoice_text += f"📦 **نحوه ارسال:** {shipping_method}\n\n"
    
    invoice_text += "═" * 25 + "\n\n"
    invoice_text += "❓ **آیا همه اطلاعات مورد تایید است؟**"
    
    from keyboards import final_confirmation_keyboard
    
    context.user_data['confirming_order'] = order_id
    
    if query:
        await query.message.reply_text(
            invoice_text,
            parse_mode='Markdown',
            reply_markup=final_confirmation_keyboard()
        )
    else:
        await context.bot.send_message(
            user_id,
            invoice_text,
            parse_mode='Markdown',
            reply_markup=final_confirmation_keyboard()
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
    db.update_order_status(order_id, 'confirmed')
    
    user_id = update.effective_user.id
    context.bot_data.pop(f'pending_shipping_{user_id}', None)
    context.user_data.pop('confirming_order', None)
    
    from keyboards import user_main_keyboard
    
    await query.message.reply_text(
        "✅ **سفارش شما ثبت نهایی شد!**\n\n"
        "📦 سفارش شما به‌زودی ارسال خواهد شد.\n\n"
        "🙏 از خرید شما سپاسگزاریم!",
        parse_mode='Markdown',
        reply_markup=user_main_keyboard()
    )
    
    from config import ADMIN_ID
    await context.bot.send_message(
        ADMIN_ID,
        f"✅ سفارش #{order_id} توسط کاربر تایید نهایی شد و آماده ارسال است."
    )


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
    text = "📞 <b>راه‌های ارتباطی با ما:</b>\n\n"
    text += "📱 شماره تماس: <code>09123834869</code>\n"
    text += "🆔 آیدی تلگرام: @manto_omde_erfan\n"
    text += "📢 کانال ما: @manto_omdeh_erfan\n\n"
    text += "🕐 پاسخگویی: همه روزه ۹ صبح تا ۹ شب"
    
    await update.message.reply_text(text, parse_mode='HTML')
