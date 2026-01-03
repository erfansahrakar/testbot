"""
مدیریت حذف و ویرایش پک‌ها توسط ادمین
این فایل باید به همراه admin.py و admin_extended.py استفاده شود
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from keyboards import admin_main_keyboard


async def is_admin(user_id):
    """بررسی ادمین بودن کاربر"""
    return user_id == ADMIN_ID


async def manage_packs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی مدیریت پک‌ها"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(update.effective_user.id):
        return
    
    product_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    product = db.get_product(product_id)
    packs = db.get_packs(product_id)
    
    if not product:
        await query.answer("❌ محصول یافت نشد!", show_alert=True)
        return
    
    if not packs:
        await query.message.reply_text(
            "⚠️ این محصول هیچ پکی ندارد!\n\n"
            "ابتدا پک اضافه کنید.",
            reply_markup=admin_main_keyboard()
        )
        return
    
    _, prod_name, *_ = product
    
    text = f"📦 **مدیریت پک‌های محصول:**\n"
    text += f"🏷 {prod_name}\n\n"
    text += "📋 پک‌های موجود:\n\n"
    
    keyboard = []
    
    for idx, pack in enumerate(packs):
        pack_id, _, pack_name, quantity, price = pack
        
        text += f"{idx + 1}. **{pack_name}**\n"
        text += f"   🔢 تعداد: {quantity}\n"
        text += f"   💰 قیمت: {price:,.0f} تومان\n\n"
        
        # دکمه‌های هر پک
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ ویرایش {pack_name}",
                callback_data=f"edit_pack:{pack_id}"
            ),
            InlineKeyboardButton(
                f"🗑 حذف {pack_name}",
                callback_data=f"confirm_delete_pack:{pack_id}:{product_id}"
            )
        ])
    
    # دکمه بازگشت
    keyboard.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data=f"back_to_product:{product_id}"
        )
    ])
    
    await query.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def confirm_delete_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست تایید حذف پک"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(update.effective_user.id):
        return
    
    data = query.data.split(":")
    pack_id = int(data[1])
    product_id = int(data[2])
    
    db = context.bot_data['db']
    pack = db.get_pack(pack_id)
    
    if not pack:
        await query.answer("❌ پک یافت نشد!", show_alert=True)
        return
    
    _, _, pack_name, quantity, price = pack
    
    text = f"⚠️ **تایید حذف پک**\n\n"
    text += f"📦 {pack_name}\n"
    text += f"🔢 تعداد: {quantity}\n"
    text += f"💰 قیمت: {price:,.0f} تومان\n\n"
    text += "❓ آیا مطمئن هستید که می‌خواهید این پک را حذف کنید؟"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"delete_pack_final:{pack_id}:{product_id}"),
            InlineKeyboardButton("❌ خیر، انصراف", callback_data=f"manage_packs:{product_id}")
        ]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_pack_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف نهایی پک"""
    query = update.callback_query
    await query.answer("🗑 پک حذف شد!")
    
    if not await is_admin(update.effective_user.id):
        return
    
    data = query.data.split(":")
    pack_id = int(data[1])
    product_id = int(data[2])
    
    db = context.bot_data['db']
    
    # حذف پک
    db.delete_pack(pack_id)
    
    await query.edit_message_text(
        "✅ **پک با موفقیت حذف شد!**",
        parse_mode='Markdown'
    )
    
    # بازگشت به لیست پک‌ها
    # ایجاد یک Update جدید برای فراخوانی مجدد
    from telegram import CallbackQuery
    new_query = CallbackQuery(
        id=query.id,
        from_user=query.from_user,
        chat_instance=query.chat_instance,
        message=query.message,
        data=f"manage_packs:{product_id}"
    )
    
    # تاخیر کوتاه و نمایش دوباره لیست
    import asyncio
    await asyncio.sleep(1)
    
    # بازگشت به منوی مدیریت پک‌ها
    packs = db.get_packs(product_id)
    
    if not packs:
        await query.message.reply_text(
            "✅ همه پک‌ها حذف شدند!\n\n"
            "این محصول دیگر پکی ندارد.",
            reply_markup=admin_main_keyboard()
        )
    else:
        # نمایش دوباره لیست پک‌های باقی‌مانده
        context_copy = context
        update_copy = Update(update.update_id, callback_query=new_query)
        await manage_packs_menu(update_copy, context_copy)


async def bulk_delete_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف چندتایی پک‌ها"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(update.effective_user.id):
        return
    
    product_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    packs = db.get_packs(product_id)
    
    if not packs:
        await query.answer("❌ پکی وجود ندارد!", show_alert=True)
        return
    
    text = "🗑 **حذف دسته‌جمعی پک‌ها**\n\n"
    text += "روی پک‌هایی که می‌خواهید حذف کنید کلیک کنید:\n\n"
    
    keyboard = []
    
    for pack in packs:
        pack_id, _, pack_name, quantity, price = pack
        keyboard.append([
            InlineKeyboardButton(
                f"☐ {pack_name} - {price:,.0f} تومان",
                callback_data=f"toggle_pack:{pack_id}:{product_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🗑 حذف انتخاب شده‌ها", callback_data=f"delete_selected_packs:{product_id}"),
        InlineKeyboardButton("❌ انصراف", callback_data=f"manage_packs:{product_id}")
    ])
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # ذخیره لیست خالی برای پک‌های انتخاب شده
    context.user_data['selected_packs'] = []


# ==================== راهنمای استفاده ====================
"""
برای استفاده از این فایل، باید موارد زیر را در main.py اضافه کنید:

1. Import کردن توابع:
from handlers.admin_pack_management import (
    manage_packs_menu,
    confirm_delete_pack,
    delete_pack_final
)

2. اضافه کردن handler ها:
app.add_handler(CallbackQueryHandler(manage_packs_menu, pattern=r"^manage_packs:"))
app.add_handler(CallbackQueryHandler(confirm_delete_pack, pattern=r"^confirm_delete_pack:"))
app.add_handler(CallbackQueryHandler(delete_pack_final, pattern=r"^delete_pack_final:"))

3. در keyboards.py باید دکمه "مدیریت پک‌ها" به product_management_keyboard اضافه شود:
InlineKeyboardButton("📦 مدیریت پک‌ها", callback_data=f"manage_packs:{product_id}")
"""
