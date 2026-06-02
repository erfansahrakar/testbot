"""
سیستم فاکتورزنی برای مشتریان توسط ادمین
✨ قابلیت‌ها:
- ثبت سفارش برای کاربر خاص
- افزودن محصولات به سبد کاربر
- ویرایش و حذف آیتم‌ها
- ثبت نهایی فاکتور
- ارسال فاکتور به کاربر
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# ==================== States ====================
INVOICE_USER_ID = 200
INVOICE_SELECT_PRODUCT = 201
INVOICE_SELECT_PACK = 202
INVOICE_ITEM_QUANTITY = 203
INVOICE_ITEM_NOTES = 204
INVOICE_ADD_MORE = 205
INVOICE_DISCOUNT = 206
INVOICE_SHIPPING = 207
INVOICE_FINAL_CONFIRM = 208

# ==================== توابع Helper ====================

def format_price(price: float) -> str:
    """فرمت کردن قیمت"""
    return f"{price:,.0f}".replace(',', '٬')

def get_invoice_keyboard():
    """کیبورد منوی فاکتورزنی"""
    keyboard = [
        [InlineKeyboardButton("📝 ثبت فاکتور جدید", callback_data="invoice:new")],
        [InlineKeyboardButton("📋 فاکتورهای ثبت شده", callback_data="invoice:list")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_invoice_draft_keyboard(user_id: int):
    """کیبورد برای مدیریت پیش‌نویس فاکتور"""
    keyboard = [
        [
            InlineKeyboardButton("➕ افزودن محصول", callback_data=f"invoice_add:{user_id}"),
            InlineKeyboardButton("👁 مشاهده", callback_data=f"invoice_view:{user_id}")
        ],
        [
            InlineKeyboardButton("🗑 حذف آیتم", callback_data=f"invoice_remove:{user_id}"),
            InlineKeyboardButton("✏️ ویرایش تعداد", callback_data=f"invoice_edit:{user_id}")
        ],
        [
            InlineKeyboardButton("💰 اعمال تخفیف", callback_data=f"invoice_discount:{user_id}"),
            InlineKeyboardButton("🚚 نوع ارسال", callback_data=f"invoice_shipping:{user_id}")
        ],
        [
            InlineKeyboardButton("✅ ثبت نهایی فاکتور", callback_data=f"invoice_finalize:{user_id}")
        ],
        [
            InlineKeyboardButton("❌ لغو و حذف", callback_data=f"invoice_cancel:{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== توابع اصلی ====================

async def admin_invoice_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی فاکتورزنی"""
    query = update.callback_query if update.callback_query else None
    
    if query:
        await query.answer()
        message_func = query.message.reply_text
    else:
        message_func = update.message.reply_text
    
    text = "📝 **سیستم فاکتورزنی مشتریان**\n\n"
    text += "از این بخش می‌توانید:\n"
    text += "• فاکتور جدید برای مشتری ثبت کنید\n"
    text += "• محصولات را به سبد مشتری اضافه کنید\n"
    text += "• تخفیف و نوع ارسال تعیین کنید\n"
    text += "• فاکتور نهایی را برای مشتری ارسال کنید\n\n"
    text += "💡 مناسب برای سفارشات تلفنی یا چت خصوصی"
    
    await message_func(text, parse_mode='Markdown', reply_markup=get_invoice_keyboard())

async def invoice_new_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ثبت فاکتور جدید"""
    query = update.callback_query
    await query.answer()
    
    from keyboards import cancel_keyboard
    
    await query.message.reply_text(
        "👤 **ثبت فاکتور جدید**\n\n"
        "لطفاً User ID مشتری را وارد کنید:\n\n"
        "💡 راهنما:\n"
        "• از مشتری بخواهید /start را در ربات بزند\n"
        "• یا از لیست کاربران User ID را پیدا کنید",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return INVOICE_USER_ID

async def invoice_user_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت User ID و شروع ساخت فاکتور"""
    if update.message.text == "❌ لغو":
        from handlers.admin import admin_start
        await admin_start(update, context)
        return ConversationHandler.END
    
    try:
        user_id = int(update.message.text)
        
        # چک کردن وجود کاربر
        db = context.bot_data['db']
        user = db.get_user(user_id)
        
        if not user:
            await update.message.reply_text(
                "⚠️ **کاربر یافت نشد!**\n\n"
                "این کاربر هنوز در ربات ثبت‌نام نکرده.\n"
                "لطفاً از مشتری بخواهید ابتدا /start را در ربات بزند.",
                parse_mode='Markdown'
            )
            return INVOICE_USER_ID
        
        # ذخیره User ID در context
        context.user_data['invoice_target_user_id'] = user_id
        
        # نمایش اطلاعات کاربر
        _, username, first_name, full_name, phone, _, address, shop_name, _ = user
        
        text = f"✅ **کاربر پیدا شد**\n\n"
        text += f"👤 نام: {full_name or first_name or 'نامشخص'}\n"
        
        if shop_name:
            text += f"🏪 نام فروشگاه: {shop_name}\n"
        if phone:
            text += f"📱 تلفن: {phone}\n"
        if username:
            text += f"🆔 Username: @{username}\n"
        
        text += f"\n📝 فاکتور برای این کاربر ایجاد شد.\n"
        text += "حالا محصولات را اضافه کنید:"
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=get_invoice_draft_keyboard(user_id)
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return INVOICE_USER_ID

async def invoice_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزودن محصول به فاکتور"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split(":")[1])
    context.user_data['invoice_target_user_id'] = user_id
    
    # نمایش لیست محصولات
    db = context.bot_data['db']
    products = db.get_all_products()
    
    if not products:
        await query.answer("❌ هیچ محصولی وجود ندارد!", show_alert=True)
        return
    
    text = "📦 **انتخاب محصول**\n\n"
    text += "محصول مورد نظر را انتخاب کنید:"
    
    keyboard = []
    for product in products[:20]:  # حداکثر 20 محصول
        prod_id, name, _, _, _, _ = product
        keyboard.append([
            InlineKeyboardButton(f"📦 {name}", callback_data=f"invoice_prod:{user_id}:{prod_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"invoice_view:{user_id}")])
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def invoice_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """محصول انتخاب شد، نمایش پک‌ها"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    user_id = int(data_parts[1])
    product_id = int(data_parts[2])
    
    context.user_data['invoice_target_user_id'] = user_id
    context.user_data['invoice_product_id'] = product_id
    
    # دریافت پک‌های محصول
    db = context.bot_data['db']
    packs = db.get_packs(product_id)
    product = db.get_product(product_id)
    
    if not packs:
        await query.answer("❌ این محصول پکی ندارد!", show_alert=True)
        return
    
    prod_id, name, desc, _, _, _ = product
    
    text = f"📦 **{name}**\n\n"
    text += "پک مورد نظر را انتخاب کنید:"
    
    keyboard = []
    for pack in packs:
        pack_id, _, pack_name, quantity, price = pack
        keyboard.append([
            InlineKeyboardButton(
                f"{pack_name} - {quantity} عدد - {format_price(price)} تومان",
                callback_data=f"invoice_pack:{user_id}:{pack_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"invoice_add:{user_id}")])
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def invoice_pack_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پک انتخاب شد، دریافت تعداد"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    user_id = int(data_parts[1])
    pack_id = int(data_parts[2])
    
    context.user_data['invoice_target_user_id'] = user_id
    context.user_data['invoice_pack_id'] = pack_id
    
    from keyboards import cancel_keyboard
    
    await query.message.reply_text(
        "🔢 **تعداد**\n\n"
        "چند عدد از این پک می‌خواهید؟\n"
        "(عدد بین 1 تا 100)",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return INVOICE_ITEM_QUANTITY

async def invoice_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تعداد و افزودن به سبد"""
    if update.message.text == "❌ لغو":
        user_id = context.user_data.get('invoice_target_user_id')
        await update.message.reply_text(
            "لغو شد.",
            reply_markup=get_invoice_draft_keyboard(user_id)
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        quantity = int(update.message.text)
        
        if quantity < 1 or quantity > 100:
            await update.message.reply_text("❌ تعداد باید بین 1 تا 100 باشد!")
            return INVOICE_ITEM_QUANTITY
        
        user_id = context.user_data.get('invoice_target_user_id')
        pack_id = context.user_data.get('invoice_pack_id')
        
        # افزودن به سبد کاربر
        db = context.bot_data['db']
        
        # دریافت اطلاعات پک
        pack = db.get_pack(pack_id)
        if not pack:
            await update.message.reply_text("❌ پک یافت نشد!")
            return ConversationHandler.END
        
        _, product_id, pack_name, pack_qty, price = pack
        
        # افزودن به سبد
        db.add_to_cart(user_id, product_id, pack_id, quantity)
        
        total_price = price * quantity
        
        text = f"✅ **محصول اضافه شد**\n\n"
        text += f"📦 {pack_name}\n"
        text += f"🔢 تعداد: {quantity}\n"
        text += f"💰 قیمت واحد: {format_price(price)} تومان\n"
        text += f"💵 جمع: {format_price(total_price)} تومان\n\n"
        text += "محصول به سبد مشتری اضافه شد."
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=get_invoice_draft_keyboard(user_id)
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد وارد کنید!")
        return INVOICE_ITEM_QUANTITY

async def invoice_view_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پیش‌نویس فاکتور"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split(":")[1])
    
    db = context.bot_data['db']
    cart_items = db.get_cart(user_id)
    
    if not cart_items:
        text = "🛒 **سبد خرید خالی است**\n\n"
        text += "هنوز محصولی اضافه نشده است.\n"
        text += "از دکمه 'افزودن محصول' استفاده کنید."
    else:
        text = f"📝 **پیش‌نویس فاکتور**\n\n"
        text += f"👤 مشتری: {user_id}\n\n"
        
        total = 0
        for idx, item in enumerate(cart_items, 1):
            _, _, _, product_name, pack_name, pack_price, item_qty, _, _ = item
            item_total = pack_price * item_qty
            total += item_total
            
            text += f"{idx}. {product_name}\n"
            text += f"   📦 {pack_name}\n"
            text += f"   🔢 تعداد: {item_qty}\n"
            text += f"   💰 قیمت: {format_price(pack_price)} × {item_qty} = {format_price(item_total)} تومان\n\n"
        
        text += f"━━━━━━━━━━━━━━━━\n"
        text += f"💵 **جمع کل:** {format_price(total)} تومان"
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=get_invoice_draft_keyboard(user_id)
    )

async def invoice_finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت نهایی فاکتور و ارسال به مشتری"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split(":")[1])
    
    db = context.bot_data['db']
    cart_items = db.get_cart(user_id)
    
    if not cart_items:
        await query.answer("❌ سبد خرید خالی است!", show_alert=True)
        return
    
    # ایجاد سفارش
    items_data = []
    total_price = 0
    
    for item in cart_items:
        cart_id, _, product_id, product_name, pack_name, pack_price, item_qty, pack_id, _ = item
        item_total = pack_price * item_qty
        total_price += item_total
        
        items_data.append({
            'product_id': product_id,
            'product_name': product_name,
            'pack_id': pack_id,
            'pack_name': pack_name,
            'price': pack_price,
            'quantity': item_qty
        })
    
    # ثبت سفارش
    order_id = db.create_order(
        user_id=user_id,
        items=items_data,
        total_price=total_price,
        final_price=total_price,
        shipping_method='standard',
        admin_created=True
    )
    
    if order_id:
        # خالی کردن سبد
        db.clear_cart(user_id)
        
        await query.message.reply_text(
            f"✅ **فاکتور ثبت شد**\n\n"
            f"📋 شماره سفارش: #{order_id}\n"
            f"👤 مشتری: {user_id}\n"
            f"💰 مبلغ: {format_price(total_price)} تومان\n\n"
            f"فاکتور برای مشتری ارسال شد.",
            parse_mode='Markdown'
        )
        
        # ارسال فاکتور به مشتری
        try:
            invoice_text = "🎉 **سفارش جدید ثبت شد!**\n\n"
            invoice_text += f"📋 شماره سفارش: #{order_id}\n\n"
            invoice_text += "📦 **محصولات:**\n\n"
            
            for idx, item in enumerate(items_data, 1):
                invoice_text += f"{idx}. {item['product_name']}\n"
                invoice_text += f"   📦 {item['pack_name']}\n"
                invoice_text += f"   🔢 {item['quantity']} عدد × {format_price(item['price'])} = "
                invoice_text += f"{format_price(item['price'] * item['quantity'])} تومان\n\n"
            
            invoice_text += f"━━━━━━━━━━━━━━━━\n"
            invoice_text += f"💵 **مبلغ قابل پرداخت:** {format_price(total_price)} تومان\n\n"
            invoice_text += "لطفاً مبلغ را واریز کرده و رسید را ارسال کنید."
            
            # کیبورد پرداخت
            keyboard = [
                [InlineKeyboardButton("💳 ارسال رسید", callback_data=f"send_receipt:{order_id}")],
                [InlineKeyboardButton("💰 استفاده از اعتبار", callback_data=f"use_wallet:{order_id}")]
            ]
            
            await context.bot.send_message(
                chat_id=user_id,
                text=invoice_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"خطا در ارسال فاکتور به مشتری: {e}")
            await query.message.reply_text(
                "⚠️ فاکتور ثبت شد اما ارسال به مشتری با خطا مواجه شد.\n"
                "لطفاً به صورت دستی فاکتور را برای مشتری ارسال کنید."
            )
    else:
        await query.answer("❌ خطا در ثبت فاکتور!", show_alert=True)

async def invoice_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو و حذف پیش‌نویس فاکتور"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split(":")[1])
    
    db = context.bot_data['db']
    db.clear_cart(user_id)
    
    await query.message.reply_text(
        "❌ **فاکتور لغو شد**\n\n"
        "سبد خرید مشتری پاک شد.",
        parse_mode='Markdown',
        reply_markup=get_invoice_keyboard()
    )
