"""
مدیریت سفارشات و پرداخت‌ها
🔴 FIX باگ 3: نمایش عدد به جای پک
"""
import json
from telegram import Update
from telegram.ext import ContextTypes
from logger import log_payment, log_admin_action
from config import ADMIN_ID, MESSAGES, CARD_NUMBER, CARD_HOLDER
from keyboards import order_confirmation_keyboard, payment_confirmation_keyboard, user_main_keyboard


async def send_order_to_admin(context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """🔴 FIX باگ 3: ارسال سفارش به ادمین (با عدد)"""
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"🆕 سفارش جدید #{order_id_val}\n\n"
    text += f"👤 کاربر: {first_name} (@{username})\n"
    text += f"📝 نام: {full_name}\n"
    text += f"📞 تلفن: {phone}\n"
    text += f"📍 آدرس: {address}\n\n"
    text += "📦 آیتم‌ها:\n"
    
    for item in items:
        # 🔴 FIX باگ 3: نمایش عدد
        text += f"• {item['product']} - {item['pack']}\n"
        text += f"  تعداد: {item['quantity']} عدد\n"
        text += f"  قیمت: {item['price']:,.0f} تومان\n\n"
    
    text += f"💰 جمع کل: {total_price:,.0f} تومان\n"
    
    if discount_amount > 0:
        text += f"🎁 تخفیف: {discount_amount:,.0f} تومان\n"
        if discount_code:
            text += f"🎫 کد تخفیف: {discount_code}\n"
        text += f"💳 مبلغ نهایی: {final_price:,.0f} تومان\n"
    
    text += f"\n📅 تاریخ: {created_at}"
    
    await context.bot.send_message(
        ADMIN_ID,
        text,
        reply_markup=order_confirmation_keyboard(order_id_val)
    )


async def view_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔴 FIX باگ 3: نمایش سفارشات در انتظار (با عدد)"""
    db = context.bot_data['db']
    orders = db.get_pending_orders()
    
    if not orders:
        await update.message.reply_text("هیچ سفارش جدیدی وجود ندارد.")
        return
    
    for order in orders:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        phone = user[4] if len(user) > 4 and user[4] else "ندارد"
        full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
        address = user[6] if len(user) > 6 and user[6] else "ندارد"
        
        text = f"📋 سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"📝 نام: {full_name}\n"
        text += f"📞 {phone}\n"
        text += f"📍 {address}\n\n"
        
        for item in items:
            # 🔴 FIX باگ 3
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد\n"
        
        text += f"\n💰 جمع: {total_price:,.0f} تومان"
        
        if discount_amount > 0:
            text += f"\n🎁 تخفیف: {discount_amount:,.0f} تومان"
            text += f"\n💳 نهایی: {final_price:,.0f} تومان"
        
        await update.message.reply_text(
            text,
            reply_markup=order_confirmation_keyboard(order_id)
        )


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید سفارش توسط ادمین"""
    query = update.callback_query
    await query.answer("✅ سفارش تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, 'waiting_payment')
    
    order = db.get_order(order_id)
    user_id = order[1]
    final_price = order[5]
    
    message = MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message)
    
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد - در انتظار پرداخت"
    )


async def reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آیتم‌ها برای حذف"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    
    from keyboards import order_items_removal_keyboard
    
    text = "🗑 **حذف آیتم از سفارش**\n\n"
    text += f"📋 سفارش #{order_id}\n\n"
    text += "کدام محصول را می‌خواهید حذف کنید؟\n\n"
    
    for idx, item in enumerate(items):
        # 🔴 FIX باگ 3
        text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
        text += f"   {item['quantity']} عدد - {item['price']:,.0f} تومان\n\n"
    
    text += f"💳 جمع کل: {final_price:,.0f} تومان"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=order_items_removal_keyboard(order_id, items)
    )


async def remove_item_from_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف یک آیتم از سفارش"""
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
    
    if len(items) <= 1:
        await query.answer("⚠️ نمی‌توانید آخرین آیتم را حذف کنید! از 'رد کامل سفارش' استفاده کنید.", show_alert=True)
        return
    
    removed_item = items.pop(item_index)
    
    # محاسبه مجدد قیمت کل
    new_total = sum(item['price'] for item in items)
    
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
    
    db.cursor.execute(
        "UPDATE orders SET items = ?, total_price = ?, discount_amount = ?, final_price = ? WHERE id = ?",
        (json.dumps(items, ensure_ascii=False), new_total, new_discount, new_final, order_id)
    )
    db.conn.commit()
    
    from keyboards import order_items_removal_keyboard
    
    text = "✅ **آیتم حذف شد!**\n\n"
    text += f"❌ حذف شد: {removed_item['product']} - {removed_item['pack']}\n\n"
    text += "📋 آیتم‌های باقی‌مانده:\n\n"
    
    for idx, item in enumerate(items):
        # 🔴 FIX باگ 3
        text += f"{idx + 1}. {item['product']} - {item['pack']}\n"
        text += f"   {item['quantity']} عدد - {item['price']:,.0f} تومان\n\n"
    
    text += f"💳 جمع جدید: {new_final:,.0f} تومان\n\n"
    text += "می‌خواهید آیتم دیگری حذف کنید؟"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=order_items_removal_keyboard(order_id, items)
    )


async def reject_full_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد کامل سفارش"""
    query = update.callback_query
    await query.answer("❌ سفارش کامل رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, 'rejected')
    
    order = db.get_order(order_id)
    user_id = order[1]
    
    await context.bot.send_message(
        user_id,
        MESSAGES["order_rejected"],
        reply_markup=user_main_keyboard()
    )
    
    await query.edit_message_text(
        query.message.text + "\n\n❌ رد شد (کامل)"
    )


async def back_to_order_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به بررسی سفارش"""
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    order = db.get_order(order_id)
    
    if not order:
        await query.answer("❌ سفارش یافت نشد!", show_alert=True)
        return
    
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    phone = user[4] if len(user) > 4 and user[4] else "ندارد"
    full_name = user[3] if len(user) > 3 and user[3] else "ندارد"
    address = user[6] if len(user) > 6 and user[6] else "ندارد"
    
    text = f"📋 سفارش #{order_id}\n\n"
    text += f"👤 {first_name} (@{username})\n"
    text += f"📝 نام: {full_name}\n"
    text += f"📞 {phone}\n"
    text += f"📍 {address}\n\n"
    
    for item in items:
        # 🔴 FIX باگ 3
        text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد\n"
    
    text += f"\n💰 {final_price:,.0f} تومان"
    
    from keyboards import order_confirmation_keyboard
    
    await query.edit_message_text(
        text,
        reply_markup=order_confirmation_keyboard(order_id)
    )


async def confirm_modified_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید سفارش با تغییرات"""
    query = update.callback_query
    await query.answer("✅ سفارش با تغییرات تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, 'waiting_payment')
    
    order = db.get_order(order_id)
    user_id = order[1]
    order_id_val, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at = order
    items = json.loads(items_json)
    
    message = "✅ **سفارش شما با تغییرات تایید شد!**\n"
    message += "⚠️ مدل‌های ناموجود از فاکتور شما حذف شدند.\n\n"
    message += "📦 آیتم‌های تایید شده:\n\n"
    
    for item in items:
        # 🔴 FIX باگ 3
        message += f"• {item['product']} - {item['pack']}\n"
        message += f"  {item['quantity']} عدد - {item['price']:,.0f} تومان\n\n"
    
    message += f"💳 مبلغ قابل پرداخت: {final_price:,.0f} تومان\n\n"
    message += MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message, parse_mode='Markdown')
    
    await query.edit_message_text(
        query.message.text + "\n\n✅ تایید شد با تغییرات - در انتظار پرداخت"
    )


async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت رسید از کاربر"""
    user_id = update.effective_user.id
    db = context.bot_data['db']
    
    orders = db.get_waiting_payment_orders()
    user_order = None
    
    for order in orders:
        if order[1] == user_id:
            user_order = order
            break
    
    if not user_order:
        await update.message.reply_text("شما سفارش در انتظار پرداختی ندارید.")
        return
    
    order_id = user_order[0]
    photo = update.message.photo[-1]
    
    db.add_receipt(order_id, photo.file_id)
    db.update_order_status(order_id, 'receipt_sent')
    
    await update.message.reply_text(MESSAGES["receipt_received"])
    
    order = db.get_order(order_id)
    items = json.loads(order[2])
    final_price = order[5]
    user = db.get_user(user_id)
    
    first_name = user[2] if len(user) > 2 else "کاربر"
    username = user[1] if len(user) > 1 and user[1] else "ندارد"
    
    text = f"💳 رسید سفارش #{order_id}\n\n"
    text += f"👤 {first_name} (@{username})\n"
    text += f"💰 مبلغ: {final_price:,.0f} تومان\n\n"
    
    for item in items:
        # 🔴 FIX باگ 3
        text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد\n"
    
    await context.bot.send_photo(
        ADMIN_ID,
        photo.file_id,
        caption=text,
        reply_markup=payment_confirmation_keyboard(order_id)
    )


async def view_payment_receipts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش رسیدهای در انتظار تایید"""
    db = context.bot_data['db']
    
    query_result = db.cursor.execute(
        "SELECT * FROM orders WHERE status = 'receipt_sent' ORDER BY created_at DESC"
    ).fetchall()
    
    if not query_result:
        await update.message.reply_text("هیچ رسیدی در انتظار تایید نیست.")
        return
    
    for order in query_result:
        order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt_photo, shipping_method, created_at = order
        items = json.loads(items_json)
        user = db.get_user(user_id)
        
        first_name = user[2] if len(user) > 2 else "کاربر"
        username = user[1] if len(user) > 1 and user[1] else "ندارد"
        
        text = f"💳 رسید سفارش #{order_id}\n\n"
        text += f"👤 {first_name} (@{username})\n"
        text += f"💰 {final_price:,.0f} تومان\n\n"
        
        for item in items:
            # 🔴 FIX باگ 3
            text += f"• {item['product']} ({item['pack']}) - {item['quantity']} عدد\n"
        
        if receipt_photo:
            await update.message.reply_photo(
                receipt_photo,
                caption=text,
                reply_markup=payment_confirmation_keyboard(order_id)
            )


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید پرداخت توسط ادمین
    ✅ FIX: ترتیب صحیح log_payment"""
    query = update.callback_query
    await query.answer("✅ پرداخت تایید شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    # ✅ FIX: اول تغییر وضعیت
    db.update_order_status(order_id, 'payment_confirmed')
    
    # ✅ FIX: بعد لاگ پرداخت
    order = db.get_order(order_id)
    user_id = order[1]
    log_payment(order_id, user_id, "confirmed")
    
    from keyboards import shipping_method_keyboard
    
    await context.bot.send_message(
        user_id,
        "✅ رسید شما تایید شد!\n\n"
        "📦 لطفاً نحوه ارسال خود را انتخاب کنید:",
        reply_markup=shipping_method_keyboard()
    )
    
    context.bot_data[f'pending_shipping_{user_id}'] = order_id
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ تایید شد - منتظر انتخاب نحوه ارسال"
    

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد پرداخت توسط ادمین"""
    query = update.callback_query
    await query.answer("❌ رسید رد شد")
    
    order_id = int(query.data.split(":")[1])
    db = context.bot_data['db']
    
    db.update_order_status(order_id, 'waiting_payment')
    
    order = db.get_order(order_id)
    user_id = order[1]
    final_price = order[5]
    
    message = MESSAGES["payment_rejected"] + "\n\n"
    message += MESSAGES["order_confirmed"].format(
        amount=f"{final_price:,.0f}",
        card=CARD_NUMBER,
        holder=CARD_HOLDER
    )
    
    await context.bot.send_message(user_id, message)
    
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ رد شد - منتظر رسید جدید"
    )
