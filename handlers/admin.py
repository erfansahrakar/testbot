"""
هندلرهای مربوط به پنل ادمین
✅ بروزرسانی شده با Cache Invalidation
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID, MESSAGES, CHANNEL_USERNAME
from validators import Validators
from logger import log_admin_action
from states import PRODUCT_NAME, PRODUCT_DESC, PRODUCT_PHOTO, PACK_NAME, PACK_QUANTITY, PACK_PRICE
from keyboards import (
    admin_main_keyboard, 
    product_management_keyboard,
    back_to_products_keyboard,
    cancel_keyboard
)


async def is_admin(user_id):
    """بررسی ادمین بودن کاربر"""
    return user_id == ADMIN_ID


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع پنل ادمین"""
    if not await is_admin(update.effective_user.id):
        return
    
    await update.message.reply_text(
        MESSAGES["start_admin"],
        reply_markup=admin_main_keyboard()
    )


async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع افزودن محصول"""
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 نام محصول را وارد کنید:",
        reply_markup=cancel_keyboard()
    )
    return PRODUCT_NAME


async def product_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام محصول - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    name = update.message.text
    
    is_valid, error_msg, cleaned_name = Validators.validate_product_name(name)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return PRODUCT_NAME
    
    context.user_data['product_name'] = cleaned_name
    await update.message.reply_text("📄 توضیحات محصول را وارد کنید:")
    return PRODUCT_DESC


async def product_desc_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت توضیحات محصول"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    context.user_data['product_desc'] = update.message.text
    await update.message.reply_text("📷 عکس محصول را ارسال کنید:")
    return PRODUCT_PHOTO


async def product_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عکس محصول"""
    if not update.message.photo:
        await update.message.reply_text("❌ لطفاً یک عکس ارسال کنید!")
        return PRODUCT_PHOTO
    
    photo = update.message.photo[-1]
    context.user_data['product_photo'] = photo.file_id
    
    db = context.bot_data['db']
    
    product_id = db.add_product(
        context.user_data['product_name'],
        context.user_data['product_desc'],
        context.user_data['product_photo']
    )
    
    log_admin_action(
        update.effective_user.id, 
        "افزودن محصول", 
        f"ID: {product_id}"
    )
    
    # 🆕 Invalidate cache
    cache_manager = context.bot_data.get('cache_manager')
    if cache_manager:
        cache_manager.invalidate_pattern("products:")
    
    await update.message.reply_text(
        MESSAGES["product_added"],
        reply_markup=admin_main_keyboard()
    )
    
    await update.message.reply_text(
        f"محصول با شناسه {product_id} ثبت شد.\n\nحالا می‌توانید پک‌ها را اضافه کنید:",
        reply_markup=product_management_keyboard(product_id)
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست محصولات"""
    if not await is_admin(update.effective_user.id):
        return
    
    # 🆕 استفاده از Cache
    db_cache = context.bot_data.get('db_cache')
    db = context.bot_data['db']
    
    if db_cache:
        products = db_cache.get_all_products()
    else:
        products = db.get_all_products()
    
    if not products:
        await update.message.reply_text("هیچ محصولی ثبت نشده است.")
        return
    
    for product in products:
        product_id, name, desc, photo_id, *_ = product
        
        # 🆕 استفاده از Cache برای پک‌ها
        if db_cache:
            packs = db_cache.get_packs(product_id)
        else:
            packs = db.get_packs(product_id)
        
        text = f"🏷 {name}\n\n{desc}\n\n"
        if packs:
            text += "📦 پک‌های موجود:\n"
            for pack in packs:
                _, _, pack_name, quantity, price = pack
                text += f"• {pack_name}: {quantity} تایی - {price:,.0f} تومان\n"
        else:
            text += "⚠️ هنوز پکی تعریف نشده است."
        
        if photo_id:
            await update.message.reply_photo(
                photo_id,
                caption=text,
                reply_markup=product_management_keyboard(product_id)
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=product_management_keyboard(product_id)
            )


async def add_pack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع افزودن پک"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    product_id = int(query.data.split(":")[1])
    context.user_data['adding_pack_to'] = product_id
    
    await query.message.reply_text(
        "📦 نام پک را وارد کنید (مثال: پک ۶ تایی):",
        reply_markup=cancel_keyboard()
    )
    return PACK_NAME


async def pack_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام پک - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    name = update.message.text
    
    is_valid, error_msg, cleaned_name = Validators.validate_pack_name(name)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return PACK_NAME
    
    context.user_data['pack_name'] = cleaned_name
    await update.message.reply_text("🔢 تعداد در پک را وارد کنید (مثال: ۶):")
    return PACK_QUANTITY


async def pack_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تعداد پک - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    quantity_str = update.message.text
    
    is_valid, error_msg, quantity = Validators.validate_quantity(quantity_str, min_value=1, max_value=1000)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return PACK_QUANTITY
    
    context.user_data['pack_quantity'] = quantity
    await update.message.reply_text("💰 قیمت پک را وارد کنید (به تومان):")
    return PACK_PRICE


async def pack_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت قیمت پک - با اعتبارسنجی"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        return ConversationHandler.END
    
    price_str = update.message.text
    
    is_valid, error_msg, price = Validators.validate_price(price_str)
    
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            reply_markup=cancel_keyboard()
        )
        return PACK_PRICE
    
    db = context.bot_data['db']
    product_id = context.user_data['adding_pack_to']
    
    db.add_pack(
        product_id,
        context.user_data['pack_name'],
        context.user_data['pack_quantity'],
        price
    )
    
    # 🆕 Invalidate cache
    cache_manager = context.bot_data.get('cache_manager')
    if cache_manager:
        cache_manager.invalidate(f"packs:{product_id}")
    
    await update.message.reply_text(
        MESSAGES["pack_added"],
        reply_markup=admin_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def view_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پک‌های یک محصول"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    
    # 🆕 استفاده از Cache
    db_cache = context.bot_data.get('db_cache')
    db = context.bot_data['db']
    
    if db_cache:
        packs = db_cache.get_packs(product_id)
    else:
        packs = db.get_packs(product_id)
    
    if not packs:
        await query.message.reply_text("هیچ پکی برای این محصول تعریف نشده است.")
        return
    
    text = "📦 پک‌های موجود:\n\n"
    for pack in packs:
        pack_id, _, name, quantity, price = pack
        text += f"🆔 {pack_id}\n"
        text += f"📦 {name}\n"
        text += f"🔢 تعداد: {quantity}\n"
        text += f"💰 قیمت: {price:,.0f} تومان\n\n"
    
    await query.message.reply_text(text, reply_markup=back_to_products_keyboard())


async def get_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال محصول به کانال + ذخیره message_id"""
    query = update.callback_query
    await query.answer()
    
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "your_channel_username":
        await query.message.reply_text(
            "⚠️ لطفاً ابتدا username کانال را در فایل config.py تنظیم کنید:\n\n"
            "CHANNEL_USERNAME = \"channel_username\""
        )
        return
    
    product_id = int(query.data.split(":")[1])
    
    # 🆕 استفاده از Cache
    db_cache = context.bot_data.get('db_cache')
    db = context.bot_data['db']
    
    if db_cache:
        product = db_cache.get_product(product_id)
        packs = db_cache.get_packs(product_id)
    else:
        product = db.get_product(product_id)
        packs = db.get_packs(product_id)
    
    if not product:
        await query.message.reply_text("❌ محصول یافت نشد.")
        return
    
    if not packs:
        await query.message.reply_text("⚠️ ابتدا حداقل یک پک برای این محصول تعریف کنید.")
        return
    
    _, name, desc, photo_id, *_ = product
    
    caption = f"🏷 **{name}**\n\n"
    caption += f"{desc}\n\n"
    caption += "📦 **پک‌های موجود:**\n\n"
    
    pack_names = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم"]
    
    for idx, pack in enumerate(packs):
        _, _, pack_name, quantity, price = pack
        pack_num = pack_names[idx] if idx < len(pack_names) else f"{idx + 1}"
        caption += f"📦 پک {pack_num}: {pack_name} - {price:,.0f} تومان\n"
    
    caption += "\n💎 برای سفارش روی دکمه پک مورد نظر کلیک کنید 👇"
    
    keyboard = []
    
    for idx, pack in enumerate(packs):
        pack_id, prod_id, pack_name, quantity, price = pack
        pack_num = pack_names[idx] if idx < len(pack_names) else f"{idx + 1}"
        button_text = f"انتخاب پک {pack_num}"
        keyboard.append([InlineKeyboardButton(
            button_text, 
            callback_data=f"select_pack:{product_id}:{pack_id}"
        )])
    
    bot_username = context.bot.username
    keyboard.append([InlineKeyboardButton(
        "🛒 مشاهده سبد خرید من",
        url=f"https://t.me/{bot_username}?start=view_cart"
    )])
    
    try:
        sent_message = None
        
        if photo_id:
            sent_message = await context.bot.send_photo(
                chat_id=f"@{CHANNEL_USERNAME}",
                photo=photo_id,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            sent_message = await context.bot.send_message(
                chat_id=f"@{CHANNEL_USERNAME}",
                text=caption,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        if sent_message:
            message_id = sent_message.message_id
            success = db.save_channel_message_id(product_id, message_id)
            
            if success:
                await query.message.reply_text(
                    f"✅ محصول با موفقیت در کانال منتشر شد!\n\n"
                    f"🔗 @{CHANNEL_USERNAME}\n"
                    f"📝 Message ID: {message_id} (ذخیره شد)"
                )
            else:
                await query.message.reply_text(
                    f"⚠️ محصول ارسال شد اما message_id ذخیره نشد!\n\n"
                    f"🔗 @{CHANNEL_USERNAME}\n"
                    f"📝 Message ID: {message_id}"
                )
        
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg.lower():
            await query.message.reply_text(
                "❌ کانال یافت نشد!\n\n"
                "لطفاً مطمئن شوید:\n"
                "1️⃣ username کانال در config.py صحیح است\n"
                "2️⃣ کانال Public است\n"
                "3️⃣ ربات را Admin کانال کرده‌اید"
            )
        elif "not enough rights" in error_msg.lower():
            await query.message.reply_text(
                "❌ ربات دسترسی کافی ندارد!\n\n"
                f"لطفاً ربات را با دسترسی 'Post Messages' به عنوان Admin کانال @{CHANNEL_USERNAME} اضافه کنید."
            )
        else:
            await query.message.reply_text(f"❌ خطا در ارسال به کانال:\n{error_msg}")


async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف محصول"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(update.effective_user.id):
        return
    
    product_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    db.delete_product(product_id)
    
    # 🆕 Invalidate cache
    cache_manager = context.bot_data.get('cache_manager')
    if cache_manager:
        cache_manager.invalidate(f"product:{product_id}")
        cache_manager.invalidate(f"packs:{product_id}")
        cache_manager.invalidate_pattern("products:")
    
    await query.message.reply_text("✅ محصول حذف شد.")
    await query.message.delete()


async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار فروش"""
    if not await is_admin(update.effective_user.id):
        return
    
    # 🆕 استفاده از Cache
    db_cache = context.bot_data.get('db_cache')
    db = context.bot_data['db']
    
    if db_cache:
        stats = db_cache.get_statistics()
    else:
        stats = db.get_statistics()
    
    text = "📊 **آمار فروشگاه**\n"
    text += "═" * 25 + "\n\n"
    
    text += f"📦 تعداد کل سفارشات: {stats['total_orders']}\n"
    text += f"🆕 سفارشات امروز: {stats['today_orders']}\n"
    text += f"⏳ سفارشات در انتظار: {stats['pending_orders']}\n\n"
    
    text += f"💰 درآمد کل: {stats['total_income']:,.0f} تومان\n"
    text += f"📈 درآمد امروز: {stats['today_income']:,.0f} تومان\n\n"
    
    text += f"👥 تعداد کاربران: {stats['total_users']}\n"
    text += f"🏷 تعداد محصولات: {stats['total_products']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')
