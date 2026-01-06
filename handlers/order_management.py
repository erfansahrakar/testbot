"""
🔴 FIX: مدیریت پیشرفته آیتم‌های سفارش (ایمن سازی شده)
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
    """🔥 افزایش تعداد (Safe)"""
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
        
        # ✅ FIX: استفاده از کلید دیکشنری به جای Unpacking
        items = json.loads(order['items'])
        
        if item_index < 0 or item_index >= len(items):
            await query.answer("❌ آیتم نامعتبر!", show_alert=True)
            return
        
        pack_quantity = items[item_index].get('pack_quantity', 1)
        items[item_index]['quantity'] += pack_quantity
        
        await update_order_prices(db, order_id, items, order['discount_code'])
        await show_updated_order_items(query, order_id, items, db)
    
    except Exception as e:
        logger.error(f"❌ Error in increase: {e}", exc_info=True)
        await query.answer("❌ خطا رخ داد!", show_alert=True)

async def decrease_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 کاهش تعداد (Safe)"""
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
        
        items = json.loads(order['items'])
        
        if item_index < 0 or item_index >= len(items):
            await query.answer("❌ آیتم نامعتبر!", show_alert=True)
            return
        
        pack_quantity = items[item_index].get('pack_quantity', 1)
        current_quantity = items[item_index]['quantity']
        
        if current_quantity <= pack_quantity:
            await query.answer("⚠️ تعداد نمی‌تواند کمتر از 1 پک شود! برای حذف از '🗑 حذف آیتم' استفاده کنید.", show_alert=True)
            return
        
        items[item_index]['quantity'] -= pack_quantity
        await query.answer()
        
        await update_order_prices(db, order_id, items, order['discount_code'])
        await show_updated_order_items(query, order_id, items, db)
    
    except Exception as e:
        logger.error(f"❌ Error in decrease: {e}", exc_info=True)
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
        
        items = json.loads(order['items'])
        
        if item_index < 0 or item_index >= len(items):
            await query.answer("❌ آیتم نامعتبر!", show_alert=True)
            return ConversationHandler.END
        
        item = items[item_index]
        pack_quantity = item.get('pack_quantity', 1)
        
        context.user_data['editing_order_id'] = order_id
        context.user_data['editing_item_index'] = item_index
        context.user_data['editing_discount_code'] = order['discount_code']
        
        await query.message.reply_text(
            f"✏️ **ویرایش تعداد**\n📦 {item['product']} - {item['pack']}\n🔢 تعداد فعلی: {item['quantity']}\n📦 هر پک: {pack_quantity}\n\n💡 تعداد جدید را وارد کنید (عدد):\n⚠️ برای حذف، عدد 0 وارد کنید.",
            parse_mode='Markdown', reply_markup=cancel_keyboard()
        )
        return EDIT_ITEM_QUANTITY
    
    except Exception as e:
        logger.error(f"❌ Error in edit start: {e}", exc_info=True)
        await query.answer("❌ خطا رخ داد!", show_alert=True)
        return ConversationHandler.END

async def edit_item_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ لغو":
        await update.message.reply_text("لغو شد.", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    try:
        new_quantity = int(update.message.text)
        if new_quantity < 0: raise ValueError
        
        order_id = context.user_data.get('editing_order_id')
        item_index = context.user_data.get('editing_item_index')
        discount_code = context.user_data.get('editing_discount_code')
        
        db = context.bot_data['db']
        order = db.get_order(order_id)
        if not order:
            await update.message.reply_text("❌ سفارش یافت نشد!", reply_markup=admin_main_keyboard())
            context.user_data.clear()
            return ConversationHandler.END
        
        items = json.loads(order['items'])
        
        if new_quantity == 0:
            if len(items) <= 1:
                await update.message.reply_text("⚠️ نمی‌توانید آخرین آیتم را حذف کنید! از 'رد کامل سفارش' استفاده کنید.", reply_markup=admin_main_keyboard())
                context.user_data.clear()
                return ConversationHandler.END
            
            removed_item = items.pop(item_index)
            await update_order_prices(db, order_id, items, discount_code)
            
            # Show updated list logic...
            await update.message.reply_text(f"🗑 **{removed_item['product']}** حذف شد!", parse_mode='Markdown', reply_markup=order_items_removal_keyboard(order_id, items))
            context.user_data.clear()
            return ConversationHandler.END
        
        else:
            context.user_data['new_quantity'] = new_quantity
            context.user_data['old_quantity'] = items[item_index]['quantity']
            
            keyboard = [[InlineKeyboardButton("⏭ رد کردن (بدون توضیحات)", callback_data=f"skip_notes:{order_id}:{item_index}")],
                        [InlineKeyboardButton("❌ لغو", callback_data=f"cancel_edit:{order_id}")]]
            
            await update.message.reply_text(f"✅ تعداد به **{new_quantity}** تغییر کرد!\n\n📝 **توضیحات اختیاری:** (مثل رنگ/سایز)\n", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            return EDIT_ITEM_NOTES

    except ValueError:
        await update.message.reply_text("❌ لطفاً عدد صحیح وارد کنید!", reply_markup=cancel_keyboard())
        return EDIT_ITEM_QUANTITY
    except Exception as e:
        logger.error(f"❌ Error in received: {e}", exc_info=True)
        await update.message.reply_text("❌ خطای غیرمنتظره!", reply_markup=admin_main_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

async def edit_item_notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    order_id = context.user_data.get('editing_order_id')
    item_index = context.user_data.get('editing_item_index')
    new_quantity = context.user_data.get('new_quantity')
    
    db = context.bot_data['db']
    order = db.get_order(order_id)
    items = json.loads(order['items'])
    
    items[item_index]['quantity'] = new_quantity
    items[item_index]['admin_notes'] = notes
    
    await update_order_prices(db, order_id, items, order['discount_code'])
    await update.message.reply_text(f"✅ ثبت شد!\nتوضیحات: {notes}", reply_markup=admin_main_keyboard())
    await show_updated_items_with_notes(update, order_id, items, db)
    context.user_data.clear()
    return ConversationHandler.END

async def skip_item_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    order_id, item_index = int(data[1]), int(data[2])
    
    new_quantity = context.user_data.get('new_quantity')
    db = context.bot_data['db']
    order = db.get_order(order_id)
    items = json.loads(order['items'])
    
    items[item_index]['quantity'] = new_quantity
    items[item_index]['admin_notes'] = None
    
    await update_order_prices(db, order_id, items, order['discount_code'])
    await query.edit_message_text(f"✅ تعداد به {new_quantity} تغییر کرد!")
    await show_updated_items_with_notes(query, order_id, items, db)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_item_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ لغو شد")
    await query.edit_message_text("❌ ویرایش لغو شد.", reply_markup=admin_main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def show_updated_items_with_notes(update_or_query, order_id, items, db):
    try:
        text = "📋 **لیست به‌روز شده:**\n\n"
        for idx, item in enumerate(items):
            text += f"{idx + 1}. {item['product']} - {item['pack']}\n   🔢 تعداد: {item['quantity']}\n"
            if item.get('admin_notes'): text += f"   📝 توضیحات: {item['admin_notes']}\n"
            text += f"   💰 {item['price']:,.0f} تومان\n\n"
        
        order = db.get_order(order_id)
        text += f"💳 **جمع کل: {order['final_price']:,.0f} تومان**\n\n"
        if len(items) == 1: text += "⚠️ این آخرین آیتم است!\n"
        
        markup = order_items_removal_keyboard(order_id, items)
        if hasattr(update_or_query, 'edit_message_text'):
            await update_or_query.edit_message_text(text, parse_mode='Markdown', reply_markup=markup)
        else:
            await update_or_query.reply_text(text, parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        logger.error(f"❌ Error show updated: {e}", exc_info=True)

async def update_order_prices(db, order_id, items, discount_code=None):
    try:
        new_total = 0
        for item in items:
            unit_price = item.get('unit_price')
            if not unit_price:
                pq = item.get('pack_quantity', 1)
                pp = item.get('pack_price', item.get('price', 0))
                unit_price = pp / pq if pq > 0 else 0
                item['unit_price'] = unit_price
            item['price'] = unit_price * item['quantity']
            new_total += item['price']
        
        new_discount, new_final = 0, new_total
        if discount_code:
            d_info = db.get_discount(discount_code)
            if d_info:
                # Assuming d_info is Row/Tuple, need safe unpacking or index access.
                # Since db.get_discount returns select *, it has: id, code, type, value, min...
                d_type, d_val = d_info['type'], d_info['value']
                d_min = d_info['min_purchase']
                if new_total >= d_min:
                    if d_type == 'percentage':
                        new_discount = new_total * (d_val / 100)
                        if d_info['max_discount'] and new_discount > d_info['max_discount']:
                            new_discount = d_info['max_discount']
                    else:
                        new_discount = d_val
                    new_final = new_total - new_discount

        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET items=?, total_price=?, discount_amount=?, final_price=? WHERE id=?", 
                       (json.dumps(items, ensure_ascii=False), new_total, new_discount, new_final, order_id))
        conn.commit()
    except Exception as e:
        logger.error(f"❌ DB Update Error: {e}", exc_info=True)
        raise

async def show_updated_order_items(query, order_id, items, db):
    # Same as show_updated_items_with_notes but specifically for query edit
    await show_updated_items_with_notes(query, order_id, items, db)
