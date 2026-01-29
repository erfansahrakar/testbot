"""
🔴 FIX: مدیریت پیشرفته آیتم‌های سفارش

"""
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from states import EDIT_ITEM_QUANTITY
from keyboards import order_items_removal_keyboard, cancel_keyboard, admin_main_keyboard
import logging

logger = logging.getLogger(__name__)

# State جدید برای توضیحات
EDIT_ITEM_NOTES = 999


async def increase_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 افزایش تعداد"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split(":")
        order_id = int(data[1])
        item_index = int(data[2])
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        # ✅ FIX: اضافه کردن expires_at
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
        
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            await query.answer("❌ خطا در خواندن آیتم‌ها!", show_alert=True)
            return
        
        # 🔥 بررسی index معتبر
        if item_index < 0 or item_index >= len(items):
            await query.answer("❌ آیتم نامعتبر!", show_alert=True)
            return
        
        # افزایش تعداد
        pack_quantity = items[item_index].get('pack_quantity', 1)
        items[item_index]['quantity'] += pack_quantity
        
        # محاسبه قیمت
        await update_order_prices(db, order_id, items, discount_code)
        
        # نمایش لیست به‌روز
        await show_updated_order_items(query, order_id, items, db)
    
    except Exception as e:
        logger.error(f"❌ Error in increase_item_quantity: {e}", exc_info=True)
        await query.answer("❌ خطا رخ داد!", show_alert=True)


async def decrease_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🔥 کاهش تعداد با چک آیتم آخر
    ✅ FIX: جلوگیری از کم شدن زیر 1 پک
    """
    query = update.callback_query
    
    try:
        data = query.data.split(":")
        order_id = int(data[1])
        item_index = int(data[2])
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return
        
        # ✅ FIX: اضافه کردن expires_at
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
        
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            await query.answer("❌ خطا در خواندن آیتم‌ها!", show_alert=True)
            return
        
        # 🔥 بررسی index معتبر
        if item_index < 0 or item_index >= len(items):
            await query.answer("❌ آیتم نامعتبر!", show_alert=True)
            return
        
        pack_quantity = items[item_index].get('pack_quantity', 1)
        current_quantity = items[item_index]['quantity']
        
        # ✅ FIX: چک کردن اگه فقط 1 پک مونده
        if current_quantity <= pack_quantity:
            await query.answer(
                "⚠️ تعداد نمی‌تواند کمتر از 1 پک شود!\n\n"
                "💡 برای حذف این آیتم از دکمه '🗑 حذف آیتم' استفاده کنید.",
                show_alert=True
            )
            return  # 🔴 جلوگیری از کم شدن
        
        # کم کردن تعداد
        items[item_index]['quantity'] -= pack_quantity
        await query.answer()
        
        # بروزرسانی قیمت‌ها
        await update_order_prices(db, order_id, items, discount_code)
        
        # نمایش لیست به‌روز
        await show_updated_order_items(query, order_id, items, db)
    
    except Exception as e:
        logger.error(f"❌ Error in decrease_item_quantity: {e}", exc_info=True)
        await query.answer("❌ خطا رخ داد!", show_alert=True)


async def edit_item_quantity_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✏️ شروع ویرایش تعداد"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split(":")
        order_id = int(data[1])
        item_index = int(data[2])
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await query.answer("❌ سفارش یافت نشد!", show_alert=True)
            return ConversationHandler.END
        
        # ✅ FIX: اضافه کردن expires_at
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        
        # 🔥 بررسی index
        if item_index < 0 or item_index >= len(items):
            await query.answer("❌ آیتم نامعتبر!", show_alert=True)
            return ConversationHandler.END
        
        item = items[item_index]
        pack_quantity = item.get('pack_quantity', 1)
        
        context.user_data['editing_order_id'] = order_id
        context.user_data['editing_item_index'] = item_index
        context.user_data['editing_discount_code'] = discount_code
        
        await query.message.reply_text(
            f"✏️ **ویرایش تعداد**\n\n"
            f"📦 {item['product']} - {item['pack']}\n"
            f"🔢 تعداد فعلی: {item['quantity']} عدد\n"
            f"📦 هر پک: {pack_quantity} عدد\n\n"
            f"💡 لطفاً تعداد جدید را به **عدد** وارد کنید:\n"
            f"مثال: 3، 6، 12 یا هر عدد دیگری\n\n"
            f"ℹ️ می‌توانید هر عددی (حتی کمتر از پک) وارد کنید\n"
            f"⚠️ برای حذف آیتم، عدد 0 وارد کنید.",
            parse_mode='Markdown',
            reply_markup=cancel_keyboard()
        )
        
        return EDIT_ITEM_QUANTITY
    
    except Exception as e:
        logger.error(f"❌ Error in edit_item_quantity_start: {e}", exc_info=True)
        await query.answer("❌ خطا رخ داد!", show_alert=True)
        return ConversationHandler.END


async def edit_item_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت تعداد جدید - بدون محدودیت مضرب"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        new_quantity = int(update.message.text)
        
        if new_quantity < 0:
            await update.message.reply_text(
                "❌ تعداد نمی‌تواند منفی باشد!\n"
                "لطفاً دوباره وارد کنید:",
                reply_markup=cancel_keyboard()
            )
            return EDIT_ITEM_QUANTITY
        
        order_id = context.user_data.get('editing_order_id')
        item_index = context.user_data.get('editing_item_index')
        discount_code = context.user_data.get('editing_discount_code')
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await update.message.reply_text(
                "❌ سفارش یافت نشد!",
                reply_markup=admin_main_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        # ✅ FIX: اضافه کردن expires_at
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code_db, status, receipt, shipping_method, created_at, expires_at = order
        items = json.loads(items_json)
        
        # 🔥 بررسی index
        if item_index < 0 or item_index >= len(items):
            await update.message.reply_text(
                "❌ آیتم نامعتبر!",
                reply_markup=admin_main_keyboard()
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        # 🔥 اگر تعداد صفر شد (حذف)
        if new_quantity == 0:
            # 🔴 چک آیتم آخر
            if len(items) <= 1:
                await update.message.reply_text(
                    "⚠️ **نمی‌توانید آخرین آیتم را حذف کنید!**\n\n"
                    "💡 اگر می‌خواهید کل سفارش رد بشه،\n"
                    "از دکمه 'رد کامل سفارش' استفاده کنید.",
                    parse_mode='Markdown',
                    reply_markup=admin_main_keyboard()
                )
                context.user_data.clear()
                return ConversationHandler.END
            
            # حذف آیتم
            removed_item = items.pop(item_index)
            await update.message.reply_text(
                f"🗑 **{removed_item['product']}** حذف شد!",
                parse_mode='Markdown',
                reply_markup=admin_main_keyboard()
            )
            
            # 🔥 محاسبه صحیح قیمت
            await update_order_prices(db, order_id, items, discount_code)
            
            # نمایش لیست به‌روز
            text = "📋 **لیست به‌روز شده:**\n\n"
            
            for idx, item in enumerate(items):
                text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
                text += f"   🔢 تعداد: {item['quantity']} عدد\n"
                text += f"   💰 {item['price']:,.0f} تومان\n\n"
            
            order_updated = db.get_order(order_id)
            final_price_updated = order_updated[5]
            
            text += f"💳 **مبلغ نهایی جدید: {final_price_updated:,.0f} تومان**"
            
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=order_items_removal_keyboard(order_id, items)
            )
            
            context.user_data.clear()
            return ConversationHandler.END
        
        else:
            # ✅ ذخیره تعداد جدید و درخواست توضیحات
            context.user_data['new_quantity'] = new_quantity
            context.user_data['old_quantity'] = items[item_index]['quantity']
            
            # کیبورد برای رد کردن توضیحات
            keyboard = [
                [InlineKeyboardButton("⏭ رد کردن (بدون توضیحات)", callback_data=f"skip_notes:{order_id}:{item_index}")],
                [InlineKeyboardButton("❌ لغو", callback_data=f"cancel_edit:{order_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ تعداد به **{new_quantity}** عدد تغییر کرد!\n\n"
                f"📝 **توضیحات اختیاری:**\n\n"
                f"اگر می‌خواهید توضیحی اضافه کنید (مثل رنگ‌های موجود)، "
                f"لطفاً آن را تایپ کنید.\n\n"
                f"مثال: «مشکی و آبی» یا «سایز L و XL»\n\n"
                f"💡 این توضیحات برای مشتری نمایش داده می‌شود.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            return EDIT_ITEM_NOTES
    
    except ValueError:
        await update.message.reply_text(
            "❌ لطفاً یک عدد صحیح وارد کنید!\n"
            "مثال: 3 یا 6 یا 0 (برای حذف)",
            reply_markup=cancel_keyboard()
        )
        return EDIT_ITEM_QUANTITY
    
    except Exception as e:
        logger.error(f"❌ Error in edit_item_quantity_received: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ خطای غیرمنتظره رخ داد!",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END


async def edit_item_notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت توضیحات اختیاری"""
    notes = update.message.text.strip()
    
    order_id = context.user_data.get('editing_order_id')
    item_index = context.user_data.get('editing_item_index')
    discount_code = context.user_data.get('editing_discount_code')
    new_quantity = context.user_data.get('new_quantity')
    old_quantity = context.user_data.get('old_quantity')
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await update.message.reply_text(
            "❌ سفارش یافت نشد!",
            reply_markup=admin_main_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ FIX: اضافه کردن expires_at
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code_db, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    
    # تغییر تعداد و افزودن توضیحات
    items[item_index]['quantity'] = new_quantity
    items[item_index]['admin_notes'] = notes  # ذخیره توضیحات
    
    # 🔥 محاسبه صحیح قیمت
    await update_order_prices(db, order_id, items, discount_code)
    
    await update.message.reply_text(
        f"✅ **تغییرات ثبت شد!**\n\n"
        f"تعداد: {old_quantity} → {new_quantity} عدد\n"
        f"📝 توضیحات: {notes}",
        parse_mode='Markdown',
        reply_markup=admin_main_keyboard()
    )
    
    # نمایش لیست به‌روز
    await show_updated_items_with_notes(update, order_id, items, db)
    
    context.user_data.clear()
    return ConversationHandler.END


async def skip_item_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد کردن توضیحات"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    new_quantity = context.user_data.get('new_quantity')
    old_quantity = context.user_data.get('old_quantity')
    discount_code = context.user_data.get('editing_discount_code')
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        context.user_data.clear()
        return ConversationHandler.END
    
    # ✅ FIX: اضافه کردن expires_at
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code_db, status, receipt, shipping_method, created_at, expires_at = order
    items = json.loads(items_json)
    
    # تغییر فقط تعداد (بدون توضیحات)
    items[item_index]['quantity'] = new_quantity
    items[item_index]['admin_notes'] = None  # بدون توضیحات
    
    # 🔥 محاسبه صحیح قیمت
    await update_order_prices(db, order_id, items, discount_code)
    
    await query.edit_message_text(
        f"✅ تعداد از **{old_quantity}** عدد به **{new_quantity}** عدد تغییر کرد!",
        parse_mode='Markdown'
    )
    
    # نمایش لیست به‌روز
    await show_updated_items_with_notes(query, order_id, items, db)
    
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_item_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو ویرایش"""
    query = update.callback_query
    await query.answer("❌ لغو شد")
    
    await query.edit_message_text(
        "❌ ویرایش لغو شد.",
        reply_markup=admin_main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def show_updated_items_with_notes(update_or_query, order_id, items, db):
    """نمایش لیست با توضیحات"""
    try:
        text = "📋 **لیست به‌روز شده:**\n\n"
        
        for idx, item in enumerate(items):
            text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
            text += f"   🔢 تعداد: {item['quantity']} عدد\n"
            
            # نمایش توضیحات اگر وجود داشت
            if item.get('admin_notes'):
                text += f"   📝 توضیحات: {item['admin_notes']}\n"
            
            text += f"   💰 {item['price']:,.0f} تومان\n\n"
        
        order = db.get_order(order_id)
        final_price = order[5]
        
        text += f"💳 **جمع کل: {final_price:,.0f} تومان**\n\n"
        
        # 🔥 پیام هشدار اگر 1 آیتم مونده
        if len(items) == 1:
            text += "⚠️ **این آخرین آیتم است!**\n"
            text += "برای رد کامل از دکمه زیر استفاده کنید.\n\n"
        else:
            text += "می‌خواهید تغییر دیگری بدهید؟"
        
        # تشخیص query یا message
        if hasattr(update_or_query, 'message') and hasattr(update_or_query, 'edit_message_text'):
            # اگر query بود
            await update_or_query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=order_items_removal_keyboard(order_id, items)
            )
        else:
            # اگر message بود
            await update_or_query.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=order_items_removal_keyboard(order_id, items)
            )
    
    except Exception as e:
        logger.error(f"❌ Error in show_updated_items_with_notes: {e}", exc_info=True)


async def update_order_prices(db, order_id, items, discount_code=None):
    """
    🔥 محاسبه صحیح قیمت‌ها با Try-Except
    """
    try:
        # محاسبه مبلغ کل
        new_total = 0
        
        for item in items:
            # محاسبه با unit_price
            unit_price = item.get('unit_price')
            
            if not unit_price:
                # اگر unit_price نداشت، محاسبه کن
                pack_quantity = item.get('pack_quantity', 1)
                pack_price = item.get('pack_price', item.get('price', 0))
                unit_price = pack_price / pack_quantity if pack_quantity > 0 else 0
                item['unit_price'] = unit_price
            
            # قیمت کل این آیتم
            item['price'] = unit_price * item['quantity']
            new_total += item['price']
        
        # محاسبه مجدد تخفیف
        new_discount = 0
        new_final = new_total
        
        if discount_code:
            discount_info = db.get_discount(discount_code)
            if discount_info:
                discount_type = discount_info[2]
                discount_value = discount_info[3]
                min_purchase = discount_info[4]
                max_discount = discount_info[5]
                
                if new_total >= min_purchase:
                    if discount_type == 'percentage':
                        new_discount = new_total * (discount_value / 100)
                        if max_discount and new_discount > max_discount:
                            new_discount = max_discount
                    else:
                        new_discount = discount_value
                    
                    new_final = new_total - new_discount
        
        # 🔥 بروزرسانی با Try-Except
        try:
            conn = db._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders 
                SET items = ?, total_price = ?, discount_amount = ?, final_price = ? 
                WHERE id = ?
            """, (json.dumps(items, ensure_ascii=False), new_total, new_discount, new_final, order_id))
            conn.commit()
            
            logger.info(f"✅ Order {order_id} updated: total={new_total:,.0f}, discount={new_discount:,.0f}, final={new_final:,.0f}")
        
        except Exception as e:
            logger.error(f"❌ Database update error: {e}", exc_info=True)
            raise
    
    except Exception as e:
        logger.error(f"❌ Error in update_order_prices: {e}", exc_info=True)
        raise


async def show_updated_order_items(query, order_id, items, db):
    """نمایش لیست به‌روز"""
    try:
        text = "✅ **به‌روزرسانی شد!**\n\n"
        text += "📋 آیتم‌های سفارش:\n\n"
        
        for idx, item in enumerate(items):
            text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
            text += f"   🔢 تعداد: {item['quantity']} عدد\n"
            text += f"   💰 {item['price']:,.0f} تومان\n\n"
        
        order = db.get_order(order_id)
        final_price = order[5]
        
        text += f"💳 **جمع کل: {final_price:,.0f} تومان**\n\n"
        
        # 🔥 پیام هشدار اگر 1 آیتم مونده
        if len(items) == 1:
            text += "⚠️ **این آخرین آیتم است!**\n"
            text += "برای رد کامل از دکمه زیر استفاده کنید.\n\n"
        else:
            text += "می‌خواهید تغییر دیگری بدهید؟"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=order_items_removal_keyboard(order_id, items)
        )
    
    except Exception as e:
        logger.error(f"❌ Error in show_updated_order_items: {e}", exc_info=True)
        await query.answer("❌ خطا در نمایش!", show_alert=True)
