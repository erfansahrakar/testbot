"""
توابع اضافی برای ویرایش محصولات و پک‌ها

"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID, CHANNEL_USERNAME
from states import EDIT_PRODUCT_NAME, EDIT_PRODUCT_DESC, EDIT_PRODUCT_PHOTO
from states import EDIT_PACK_NAME, EDIT_PACK_QUANTITY, EDIT_PACK_PRICE
from keyboards import (
    admin_main_keyboard,
    edit_product_keyboard,
    pack_management_keyboard,
    cancel_keyboard,
    product_management_keyboard
)


# ==================== ویرایش محصول ====================

async def edit_product_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی ویرایش محصول"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    product = db.get_product(product_id)
    
    if not product:
        await query.answer("❌ محصول یافت نشد!", show_alert=True)
        return
    
    prod_id, name, desc, photo_id, channel_msg_id, created_at = product
    
    text = f"✏️ **ویرایش محصول**\n\n"
    text += f"📦 نام: {name}\n"
    text += f"📝 توضیحات: {desc[:50]}...\n\n"
    text += "چه چیزی را می‌خواهید ویرایش کنید؟"
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=edit_product_keyboard(product_id)
    )


async def edit_product_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش نام محصول"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    context.user_data['editing_product_id'] = product_id
    
    await query.message.reply_text(
        "📝 نام جدید محصول را وارد کنید:",
        reply_markup=cancel_keyboard()
    )
    
    return EDIT_PRODUCT_NAME


async def edit_product_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام جدید محصول"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ بررسی وجود editing_product_id
    product_id = context.user_data.get('editing_product_id')
    if product_id is None:
        await update.message.reply_text(
            "❌ خطا: اطلاعات محصول یافت نشد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    new_name = update.message.text
    
    db = context.bot_data['db']
    db.update_product_name(product_id, new_name)
    
    await update.message.reply_text(
        f"✅ نام محصول به '{new_name}' تغییر کرد!",
        reply_markup=admin_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def edit_product_desc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش توضیحات محصول"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    context.user_data['editing_product_id'] = product_id
    
    await query.message.reply_text(
        "📄 توضیحات جدید محصول را وارد کنید:",
        reply_markup=cancel_keyboard()
    )
    
    return EDIT_PRODUCT_DESC


async def edit_product_desc_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت توضیحات جدید محصول"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ بررسی وجود editing_product_id
    product_id = context.user_data.get('editing_product_id')
    if product_id is None:
        await update.message.reply_text(
            "❌ خطا: اطلاعات محصول یافت نشد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    new_desc = update.message.text
    
    db = context.bot_data['db']
    db.update_product_description(product_id, new_desc)
    
    await update.message.reply_text(
        "✅ توضیحات محصول به‌روزرسانی شد!",
        reply_markup=admin_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def edit_product_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش عکس محصول"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    context.user_data['editing_product_id'] = product_id
    
    await query.message.reply_text(
        "📷 عکس جدید محصول را ارسال کنید:",
        reply_markup=cancel_keyboard()
    )
    
    return EDIT_PRODUCT_PHOTO


async def edit_product_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عکس جدید محصول"""
    if not update.message.photo:
        await update.message.reply_text("❌ لطفاً یک عکس ارسال کنید!")
        return EDIT_PRODUCT_PHOTO
    
    # ✅ بررسی وجود editing_product_id
    product_id = context.user_data.get('editing_product_id')
    if product_id is None:
        await update.message.reply_text(
            "❌ خطا: اطلاعات محصول یافت نشد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    photo_id = update.message.photo[-1].file_id
    
    db = context.bot_data['db']
    db.update_product_photo(product_id, photo_id)
    
    await update.message.reply_text(
        "✅ عکس محصول به‌روزرسانی شد!",
        reply_markup=admin_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


# ==================== ویرایش پک ====================

async def view_packs_with_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پک‌ها با دکمه ویرایش"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    packs = db.get_packs(product_id)
    
    if not packs:
        await query.message.reply_text("هیچ پکی برای این محصول تعریف نشده است.")
        return
    
    for pack in packs:
        pack_id, _, name, quantity, price = pack
        text = f"📦 **{name}**\n\n"
        text += f"🔢 تعداد: {quantity}\n"
        text += f"💰 قیمت: {price:,.0f} تومان"
        
        await query.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=pack_management_keyboard(pack_id, product_id)
        )


async def edit_pack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ویرایش پک"""
    query = update.callback_query
    await query.answer()
    
    pack_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    pack = db.get_pack(pack_id)
    
    if not pack:
        await query.answer("❌ پک یافت نشد!", show_alert=True)
        return ConversationHandler.END
    
    pack_id, product_id, name, quantity, price = pack
    
    context.user_data['editing_pack_id'] = pack_id
    context.user_data['editing_pack_product_id'] = product_id
    
    await query.message.reply_text(
        f"📦 ویرایش پک: {name}\n\n"
        f"نام جدید پک را وارد کنید:\n"
        f"(نام فعلی: {name})",
        reply_markup=cancel_keyboard()
    )
    
    return EDIT_PACK_NAME


async def edit_pack_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام جدید پک"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ بررسی وجود editing_pack_id
    pack_id = context.user_data.get('editing_pack_id')
    if pack_id is None:
        await update.message.reply_text(
            "❌ خطا: اطلاعات پک یافت نشد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    context.user_data['new_pack_name'] = update.message.text
    
    db = context.bot_data['db']
    pack = db.get_pack(pack_id)
    
    await update.message.reply_text(
        f"🔢 تعداد جدید پک را وارد کنید:\n"
        f"(تعداد فعلی: {pack[3]})"
    )
    
    return EDIT_PACK_QUANTITY


async def edit_pack_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تعداد جدید پک"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ بررسی وجود editing_pack_id
    pack_id = context.user_data.get('editing_pack_id')
    if pack_id is None:
        await update.message.reply_text(
            "❌ خطا: اطلاعات پک یافت نشد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        quantity = int(update.message.text)
        context.user_data['new_pack_quantity'] = quantity
        
        db = context.bot_data['db']
        pack = db.get_pack(pack_id)
        
        await update.message.reply_text(
            f"💰 قیمت جدید پک را وارد کنید (به تومان):\n"
            f"(قیمت فعلی: {pack[4]:,.0f})"
        )
        
        return EDIT_PACK_PRICE
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد وارد کنید!")
        return EDIT_PACK_QUANTITY


async def edit_pack_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت قیمت جدید و ذخیره"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ بررسی وجود editing_pack_id
    pack_id = context.user_data.get('editing_pack_id')
    if pack_id is None:
        await update.message.reply_text(
            "❌ خطا: اطلاعات پک یافت نشد. لطفاً دوباره تلاش کنید.",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        price = float(update.message.text.replace(',', ''))
        
        db = context.bot_data['db']
        
        db.update_pack(
            pack_id,
            context.user_data['new_pack_name'],
            context.user_data['new_pack_quantity'],
            price
        )
        
        await update.message.reply_text(
            "✅ پک با موفقیت ویرایش شد!",
            reply_markup=admin_main_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
        return EDIT_PACK_PRICE


async def delete_pack_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف پک"""
    query = update.callback_query
    await query.answer("پک حذف شد!")
    
    pack_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    db.delete_pack(pack_id)
    
    await query.message.edit_text("✅ پک حذف شد.")


# ==================== ویرایش در کانال ====================

async def edit_in_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ویرایش پست محصول در کانال
    ✅ 🆕 اضافه شده: نمایش دکمه ناموجود برای محصولات بدون پک
    """
    query = update.callback_query
    await query.answer()
    
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "your_channel_username":
        await query.message.reply_text(
            "⚠️ لطفاً ابتدا username کانال را در فایل config.py تنظیم کنید."
        )
        return
    
    product_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    product = db.get_product(product_id)
    
    if not product:
        await query.answer("❌ محصول یافت نشد!", show_alert=True)
        return
    
    prod_id, name, desc, photo_id, channel_msg_id, created_at = product
    
    if not channel_msg_id:
        await query.message.reply_text(
            "❌ این محصول هنوز در کانال ارسال نشده است!\n"
            "ابتدا از گزینه 'ارسال به کانال' استفاده کنید."
        )
        return
    
    packs = db.get_packs(product_id)
    
    # ساخت متن جدید
    caption = f"🏷 **{name}**\n\n"
    caption += f"{desc}\n\n"
    
    # 🔴 🆕 چک کردن پک‌ها - اگه نباشه دکمه ناموجود نشون بده
    if not packs or len(packs) == 0:
        # هیچ پکی وجود ندارد - محصول ناموجود
        caption += "⚠️ **متأسفانه این محصول موقتاً ناموجود است**\n\n"
        caption += "💡 برای اطلاع از موجود شدن با ما در تماس باشید:\n"
        caption += f"📞 @{CHANNEL_USERNAME}"
        
        # دکمه ناموجود
        keyboard = [
            [InlineKeyboardButton("❌ ناموجود", callback_data="out_of_stock")]
        ]
        
    else:
        # پک دارد - نمایش عادی
        caption += "📦 **پک‌های موجود:**\n\n"
        
        pack_names = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم"]
        
        for idx, pack in enumerate(packs):
            _, _, pack_name, quantity, price = pack
            pack_num = pack_names[idx] if idx < len(pack_names) else f"{idx + 1}"
            caption += f"📦 پک {pack_num}: {pack_name} - {price:,.0f} تومان\n"
        
        caption += "\n💎 برای سفارش روی دکمه پک مورد نظر کلیک کنید 👇"
        
        # ساخت کیبورد
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
    
    # ویرایش پست در کانال
    try:
        if photo_id:
            await context.bot.edit_message_caption(
                chat_id=f"@{CHANNEL_USERNAME}",
                message_id=channel_msg_id,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.edit_message_text(
                chat_id=f"@{CHANNEL_USERNAME}",
                message_id=channel_msg_id,
                text=caption,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        status_msg = "✅ پست در کانال با موفقیت ویرایش شد!\n\n"
        status_msg += f"🔗 @{CHANNEL_USERNAME}\n\n"
        
        if not packs or len(packs) == 0:
            status_msg += "⚠️ توجه: محصول بدون پک (ناموجود) نمایش داده شد"
        else:
            status_msg += f"✅ {len(packs)} پک نمایش داده شد"
        
        await query.message.reply_text(status_msg)
        
    except Exception as e:
        error_msg = str(e)
        await query.message.reply_text(f"❌ خطا در ویرایش پست کانال:\n{error_msg}")


async def back_to_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به مدیریت محصول"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split(":")[1])
    
    await query.message.delete()
    
    # نمایش دوباره دکمه‌های مدیریت
    db = context.bot_data['db']
    product = db.get_product(product_id)
    
    if product:
        prod_id, name, desc, photo_id, channel_msg_id, created_at = product
        
        text = f"🏷 {name}\n\n{desc}"
        
        if photo_id:
            await query.message.reply_photo(
                photo_id,
                caption=text,
                reply_markup=product_management_keyboard(product_id)
            )
        else:
            await query.message.reply_text(
                text,
                reply_markup=product_management_keyboard(product_id)
        )
