"""
🆕 مدیریت پیشرفته آیتم‌های سفارش با ➕/➖ و ویرایش تعداد
🔴 FIX باگ 2 + باگ 3: محاسبات صحیح + سیستم عددی
"""
import json
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from states import EDIT_ITEM_QUANTITY
from keyboards import order_items_removal_keyboard, cancel_keyboard, admin_main_keyboard


async def increase_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔴 FIX: ➕ افزایش تعداد به اندازه pack_quantity"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    
    # 🔴 FIX باگ 3: افزایش به اندازه pack_quantity
    pack_quantity = items[item_index].get('pack_quantity', 1)
    items[item_index]['quantity'] += pack_quantity
    
    # 🔴 FIX باگ 2: محاسبه صحیح قیمت
    await update_order_prices(db, order_id, items, discount_code)
    
    # نمایش لیست به‌روز
    await show_updated_order_items(query, order_id, items, db)


async def decrease_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔴 FIX: ➖ کاهش تعداد به اندازه pack_quantity"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    
    # 🔴 FIX باگ 3: کاهش به اندازه pack_quantity
    pack_quantity = items[item_index].get('pack_quantity', 1)
    items[item_index]['quantity'] -= pack_quantity
    
    # اگر تعداد صفر یا منفی شد، حذف آیتم
    if items[item_index]['quantity'] <= 0:
        if len(items) <= 1:
            await query.answer("⚠️ نمی‌توانید آخرین آیتم را حذف کنید! از 'رد کامل' استفاده کنید.", show_alert=True)
            return
        
        removed_item = items.pop(item_index)
        await query.answer(f"🗑 {removed_item['product']} حذف شد!", show_alert=True)
    
    # 🔴 FIX باگ 2: محاسبه صحیح قیمت
    await update_order_prices(db, order_id, items, discount_code)
    
    # نمایش لیست به‌روز
    await show_updated_order_items(query, order_id, items, db)


async def edit_item_quantity_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔴 FIX باگ 3: ✏️ شروع ویرایش تعداد (عدد نه پک)"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    order_id = int(data[1])
    item_index = int(data[2])
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return ConversationHandler.END
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    
    item = items[item_index]
    
    context.user_data['editing_order_id'] = order_id
    context.user_data['editing_item_index'] = item_index
    context.user_data['editing_discount_code'] = discount_code
    
    # 🔴 FIX باگ 3: نمایش به عدد
    await query.message.reply_text(
        f"✏️ **ویرایش تعداد**\n\n"
        f"📦 {item['product']} - {item['pack']}\n"
        f"🔢 تعداد فعلی: {item['quantity']} عدد\n\n"
        f"لطفاً تعداد جدید را وارد کنید (به عدد):\n"
        f"مثال: 3 یا 12 یا 18",
        parse_mode='Markdown',
        reply_markup=cancel_keyboard()
    )
    
    return EDIT_ITEM_QUANTITY


async def edit_item_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔴 FIX: دریافت تعداد جدید (عدد)"""
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        new_quantity = int(update.message.text)
        
        if new_quantity < 0:
            await update.message.reply_text("❌ تعداد نمی‌تواند منفی باشد!")
            return EDIT_ITEM_QUANTITY
        
        order_id = context.user_data['editing_order_id']
        item_index = context.user_data['editing_item_index']
        discount_code = context.user_data.get('editing_discount_code')
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        
        if not order:
            await update.message.reply_text("❌ سفارش یافت نشد!")
            context.user_data.clear()
            return ConversationHandler.END
        
        order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code_db, status, receipt, shipping_method, created_at = order
        items = json.loads(items_json)
        
        # اگر تعداد صفر شد
        if new_quantity == 0:
            if len(items) <= 1:
                await update.message.reply_text(
                    "⚠️ نمی‌توانید آخرین آیتم را حذف کنید!\n"
                    "از 'رد کامل سفارش' استفاده کنید.",
                    reply_markup=admin_main_keyboard()
                )
                context.user_data.clear()
                return ConversationHandler.END
            
            removed_item = items.pop(item_index)
            await update.message.reply_text(
                f"🗑 {removed_item['product']} حذف شد!",
                reply_markup=admin_main_keyboard()
            )
        else:
            # 🔴 FIX باگ 3: تغییر تعداد به عدد
            old_qty = items[item_index]['quantity']
            items[item_index]['quantity'] = new_quantity
            
            await update.message.reply_text(
                f"✅ تعداد از {old_qty} عدد به {new_quantity} عدد تغییر کرد!",
                reply_markup=admin_main_keyboard()
            )
        
        # 🔴 FIX باگ 2: محاسبه صحیح قیمت
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
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد صحیح وارد کنید!")
        return EDIT_ITEM_QUANTITY


async def update_order_prices(db, order_id, items, discount_code=None):
    """🔴 FIX باگ 2: محاسبه صحیح قیمت‌ها
    
    هر آیتم باید داشته باشد:
    - unit_price: قیمت هر عدد
    - quantity: تعداد عدد
    - price: قیمت کل = unit_price × quantity
    """
    # محاسبه مبلغ کل
    new_total = 0
    
    for item in items:
        # 🔴 FIX باگ 2: محاسبه صحیح با unit_price
        unit_price = item.get('unit_price')
        
        if not unit_price:
            # اگر unit_price نداشت، محاسبه می‌کنیم
            pack_quantity = item.get('pack_quantity', 1)
            pack_price = item.get('pack_price', item.get('price', 0))
            unit_price = pack_price / pack_quantity if pack_quantity > 0 else 0
            item['unit_price'] = unit_price
        
        # قیمت کل این آیتم = قیمت واحد × تعداد عدد
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
    
    # بروزرسانی در دیتابیس
    db.cursor.execute(
        "UPDATE orders SET items = ?, total_price = ?, discount_amount = ?, final_price = ? WHERE id = ?",
        (json.dumps(items, ensure_ascii=False), new_total, new_discount, new_final, order_id)
    )
    db.conn.commit()
    
    print(f"✅ باگ 2 FIX: قیمت‌ها محاسبه شدند - کل={new_total:,.0f}, تخفیف={new_discount:,.0f}, نهایی={new_final:,.0f}")


async def show_updated_order_items(query, order_id, items, db):
    """🔴 FIX باگ 3: نمایش لیست به‌روز (با عدد)"""
    text = "✅ **به‌روزرسانی شد!**\n\n"
    text += "📋 آیتم‌های سفارش:\n\n"
    
    for idx, item in enumerate(items):
        text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
        text += f"   🔢 تعداد: {item['quantity']} عدد\n"
        text += f"   💰 {item['price']:,.0f} تومان\n\n"
    
    order = db.get_order(order_id)
    final_price = order[5]
    
    text += f"💳 **جمع کل: {final_price:,.0f} تومان**\n\n"
    text += "می‌خواهید تغییر دیگری بدهید؟"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=order_items_removal_keyboard(order_id, items)
    )
