"""
کیبوردها و دکمه‌های ربات
✅ FIXED: اضافه شدن per_user_limit به unpacking در discount_list_keyboard
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

def admin_main_keyboard():
    """منوی اصلی ادمین"""
    keyboard = [
        ["🎛 داشبورد", "📊 آمار"],
        ["📥 دانلود گزارشات", "⚙️ سفارشی‌سازی پیام‌ها"],
        ["➕ افزودن محصول", "📦 لیست محصولات"],
        ["📦 سفارشات", "💳 تایید پرداخت‌ها"],
        ["🎁 مدیریت تخفیف‌ها", "📢 پیام همگانی"],
        ["📈 گزارش‌های تحلیلی", "💾 بکاپ دستی"],
        ["🏦 مدیریت کیف پول", "🧹 پاکسازی دیتابیس"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_orders_submenu_keyboard():
    """زیرمنوی سفارشات ادمین"""
    keyboard = [
        ["📋 سفارشات در انتظار تایید"],
        ["📦 سفارشات ارسال نشده"],
        ["✅ سفارشات ارسال شده"],
        ["🔙 بازگشت"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def order_shipped_keyboard(order_id):
    """دکمه ارسال شد و حذف روی فاکتور سفارش ارسال نشده"""
    keyboard = [
        [
            InlineKeyboardButton("✅ ارسال شد", callback_data=f"mark_shipped:{order_id}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"admin_delete_order:{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def user_main_keyboard():
    """منوی اصلی کاربر"""
    keyboard = [
        ["🛒 سبد خرید", "📦 سفارشات من"],
        ["💰 کیف پول من", "📍 آدرس ثبت شده من"],
        ["📞 تماس با ما", "ℹ️ راهنما"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def cancel_keyboard():
    """دکمه لغو"""
    keyboard = [["❌ لغو"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def product_inline_keyboard(product_id, packs):
    """دکمه‌های انتخاب پک برای محصول"""
    keyboard = []
    for pack in packs:
        pack_id, prod_id, name, quantity, price, *_ = pack
        button_text = f"📦 {name} - {price:,.0f} تومان"
        keyboard.append([InlineKeyboardButton(
            button_text, 
            callback_data=f"select_pack:{product_id}:{pack_id}"
        )])
    return InlineKeyboardMarkup(keyboard)


def cart_keyboard(cart_items):
    """دکمه‌های سبد خرید"""
    keyboard = []
    
    for item in cart_items:
        cart_id, product_name, pack_name, pack_qty, price, quantity = item
        
        keyboard.append([InlineKeyboardButton(
            f"📦 {product_name} - {pack_name} (×{quantity} عدد)",
            callback_data=f"cart_item_info:{cart_id}"
        )])
        
        row = []
        row.append(InlineKeyboardButton(
            f"➖ ({pack_qty})", 
            callback_data=f"cart_decrease:{cart_id}"
        ))
        row.append(InlineKeyboardButton(
            "❌ حذف", 
            callback_data=f"remove_cart:{cart_id}"
        ))
        row.append(InlineKeyboardButton(
            f"➕ ({pack_qty})", 
            callback_data=f"cart_increase:{cart_id}"
        ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🎁 کد تخفیف دارم", callback_data="apply_discount")])
    keyboard.append([InlineKeyboardButton("✅ نهایی کردن سفارش", callback_data="finalize_order")])
    keyboard.append([InlineKeyboardButton("🗑 خالی کردن سبد", callback_data="clear_cart")])
    
    return InlineKeyboardMarkup(keyboard)


def order_confirmation_keyboard(order_id):
    """دکمه‌های تایید سفارش برای ادمین"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"confirm_order:{order_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_order:{order_id}")
        ],
        [
            InlineKeyboardButton("✏️ مدیریت آیتم‌ها", callback_data=f"modify_order:{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def payment_confirmation_keyboard(order_id):
    """دکمه‌های تایید پرداخت برای ادمین"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تایید رسید", callback_data=f"confirm_payment:{order_id}"),
            InlineKeyboardButton("❌ رد رسید", callback_data=f"reject_payment:{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def product_list_menu_keyboard():
    """منوی انتخاب نوع نمایش محصولات ادمین"""
    keyboard = [
        [InlineKeyboardButton("📦 کل محصولات", callback_data="product_list:all")],
        [InlineKeyboardButton("🔍 جستجوی یک محصول خاص", callback_data="product_list:search")],
    ]
    return InlineKeyboardMarkup(keyboard)


def product_management_keyboard(product_id):
    """دکمه‌های مدیریت محصول"""
    keyboard = [
        [InlineKeyboardButton("✏️ ویرایش محصول", callback_data=f"edit_product:{product_id}")],
        [InlineKeyboardButton("➕ افزودن پک", callback_data=f"add_pack:{product_id}")],
        [InlineKeyboardButton("👁 مشاهده پک‌ها", callback_data=f"view_packs:{product_id}")],
        [InlineKeyboardButton("🗑 مدیریت پک‌ها", callback_data=f"manage_packs:{product_id}")],
        [InlineKeyboardButton("📤 ارسال به کانال", callback_data=f"send_to_channel:{product_id}")],
        [InlineKeyboardButton("🔄 ویرایش در کانال", callback_data=f"edit_in_channel:{product_id}")],
        [InlineKeyboardButton("🗑 حذف محصول", callback_data=f"delete_product:{product_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def edit_product_keyboard(product_id):
    """دکمه‌های ویرایش محصول"""
    keyboard = [
        [InlineKeyboardButton("📝 ویرایش نام", callback_data=f"edit_prod_name:{product_id}")],
        [InlineKeyboardButton("📄 ویرایش توضیحات", callback_data=f"edit_prod_desc:{product_id}")],
        [InlineKeyboardButton("📷 ویرایش عکس", callback_data=f"edit_prod_photo:{product_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_to_product:{product_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def pack_management_keyboard(pack_id, product_id):
    """دکمه‌های مدیریت پک"""
    keyboard = [
        [InlineKeyboardButton("✏️ ویرایش پک", callback_data=f"edit_pack:{pack_id}")],
        [InlineKeyboardButton("🗑 حذف پک", callback_data=f"delete_pack:{pack_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_to_product:{product_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def discount_management_keyboard():
    """منوی مدیریت تخفیف‌ها"""
    keyboard = [
        [InlineKeyboardButton("➕ ایجاد کد تخفیف", callback_data="create_discount")],
        [InlineKeyboardButton("📋 لیست تخفیف‌ها", callback_data="list_discounts")],
    ]
    return InlineKeyboardMarkup(keyboard)


def discount_list_keyboard(discounts):
    """
    لیست کدهای تخفیف
    ✅ FIXED: اضافه شدن per_user_limit به unpacking
    """
    keyboard = []
    for discount in discounts:
        # ✅ FIX: اضافه شدن per_user_limit به unpacking
        discount_id, code, type, value, min_purchase, max_discount, usage_limit, used_count, per_user_limit, start_date, end_date, is_active, created_at = discount
        status = "✅" if is_active else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{status} {code} ({used_count}/{usage_limit if usage_limit else '∞'})",
            callback_data=f"view_discount:{discount_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("➕ کد جدید", callback_data="create_discount")])
    return InlineKeyboardMarkup(keyboard)


def discount_detail_keyboard(discount_id):
    """جزئیات یک کد تخفیف"""
    keyboard = [
        [InlineKeyboardButton("🔄 فعال/غیرفعال", callback_data=f"toggle_discount:{discount_id}")],
        [InlineKeyboardButton("🗑 حذف", callback_data=f"delete_discount:{discount_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="list_discounts")],
    ]
    return InlineKeyboardMarkup(keyboard)


def discount_type_keyboard():
    """انتخاب نوع تخفیف"""
    keyboard = [
        [InlineKeyboardButton("💯 درصدی", callback_data="discount_type:percentage")],
        [InlineKeyboardButton("💰 مبلغ ثابت", callback_data="discount_type:fixed")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_to_products_keyboard():
    """دکمه بازگشت به لیست محصولات"""
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="back_to_products")]]
    return InlineKeyboardMarkup(keyboard)


def view_cart_keyboard():
    """دکمه مشاهده سبد خرید"""
    keyboard = [[InlineKeyboardButton("🛍 مشاهده سبد خرید", callback_data="view_cart")]]
    return InlineKeyboardMarkup(keyboard)


def shipping_method_keyboard():
    """دکمه‌های انتخاب نحوه ارسال"""
    keyboard = [
        [InlineKeyboardButton("🚌 ترمینال", callback_data="ship_terminal")],
        [InlineKeyboardButton("🚚 باربری", callback_data="ship_barbari")],
        [InlineKeyboardButton("📦 تیپاکس", callback_data="ship_tipax")],
        [InlineKeyboardButton("🏃 چاپار", callback_data="ship_chapar")]
    ]
    return InlineKeyboardMarkup(keyboard)


def final_confirmation_keyboard():
    """دکمه‌های تایید نهایی فاکتور"""
    keyboard = [
        [InlineKeyboardButton("✅ تایید و ثبت نهایی", callback_data="final_confirm")],
        [InlineKeyboardButton("✏️ ویرایش اطلاعات", callback_data="final_edit")]
    ]
    return InlineKeyboardMarkup(keyboard)


def final_confirmation_keyboard_with_wallet(order_id: int, wallet_balance: float, final_price: float):
    """دکمه‌های تایید نهایی فاکتور با گزینه استفاده از کیف پول"""
    keyboard = []
    if wallet_balance > 0:
        usable = min(wallet_balance, final_price)
        keyboard.append([InlineKeyboardButton(
            f"💰 استفاده از کیف پول ({usable:,.0f} تومان تخفیف)",
            callback_data=f"use_wallet_invoice:{order_id}"
        )])
    keyboard.append([InlineKeyboardButton("✅ تایید و ثبت نهایی", callback_data="final_confirm")])
    keyboard.append([InlineKeyboardButton("✏️ ویرایش اطلاعات", callback_data="final_edit")])
    return InlineKeyboardMarkup(keyboard)


def edit_address_keyboard():
    """دکمه ویرایش آدرس"""
    keyboard = [[InlineKeyboardButton("✏️ ویرایش آدرس", callback_data="edit_address")]]
    return InlineKeyboardMarkup(keyboard)


def confirm_info_keyboard():
    """دکمه‌های تایید یا ویرایش اطلاعات"""
    keyboard = [
        [InlineKeyboardButton("✅ بله، اطلاعات صحیح است", callback_data="confirm_user_info")],
        [InlineKeyboardButton("✏️ خیر، ویرایش مشخصات", callback_data="edit_user_info")]
    ]
    return InlineKeyboardMarkup(keyboard)


def order_items_removal_keyboard(order_id, items):
    """دکمه‌های مدیریت آیتم‌های سفارش"""
    keyboard = []
    
    for idx, item in enumerate(items):
        product_name = item.get('product', 'محصول')
        pack_name = item.get('pack', 'پک')
        quantity = item.get('quantity', 0)
        pack_quantity = item.get('pack_quantity', 1)
        
        info_text = f"📦 {product_name} - {pack_name} (×{quantity} عدد)"
        keyboard.append([InlineKeyboardButton(info_text, callback_data=f"item_info:{idx}")])
        
        row = []
        row.append(InlineKeyboardButton(f"➖ ({pack_quantity})", callback_data=f"decrease_item:{order_id}:{idx}"))
        row.append(InlineKeyboardButton("✏️ تعداد", callback_data=f"edit_item_qty:{order_id}:{idx}"))
        row.append(InlineKeyboardButton(f"➕ ({pack_quantity})", callback_data=f"increase_item:{order_id}:{idx}"))
        row.append(InlineKeyboardButton("❌ حذف", callback_data=f"remove_item:{order_id}:{idx}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("✅ تایید سفارش با تغییرات", callback_data=f"confirm_modified:{order_id}")])
    keyboard.append([InlineKeyboardButton("🗑 رد کامل سفارش", callback_data=f"reject_full:{order_id}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_to_order:{order_id}")])
    
    return InlineKeyboardMarkup(keyboard)


def broadcast_confirm_keyboard():
    """تایید ارسال پیام همگانی"""
    keyboard = [
        [InlineKeyboardButton("✅ بله، ارسال شود", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_broadcast")],
    ]
    return InlineKeyboardMarkup(keyboard)


def analytics_menu_keyboard():
    """منوی گزارش‌های تحلیلی"""
    keyboard = [
        [InlineKeyboardButton("📊 فروش روزانه", callback_data="analytics:sales_daily")],
        [InlineKeyboardButton("📊 فروش هفتگی", callback_data="analytics:sales_weekly")],
        [InlineKeyboardButton("📊 فروش ماهانه", callback_data="analytics:sales_monthly")],
        [InlineKeyboardButton("🏆 محبوب‌ترین محصولات", callback_data="analytics:popular")],
        [InlineKeyboardButton("⏰ ساعات شلوغی", callback_data="analytics:hourly")],
        [InlineKeyboardButton("💰 تحلیل درآمد", callback_data="analytics:revenue")],
        [InlineKeyboardButton("📈 نرخ تبدیل", callback_data="analytics:conversion")],
    ]
    return InlineKeyboardMarkup(keyboard)


def quantity_keyboard(product_id, pack_id):
    """دکمه‌های انتخاب تعداد"""
    keyboard = []
    row = []
    
    for i in range(1, 11):
        row.append(InlineKeyboardButton(
            f"{i}×", 
            callback_data=f"qty:{product_id}:{pack_id}:{i}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🛍 مشاهده سبد خرید", callback_data="view_cart")])
    
    return InlineKeyboardMarkup(keyboard)


def product_list_pagination_keyboard(current_page: int, total_pages: int):
    """
    کیبورد pagination برای لیست محصولات
    
    Args:
        current_page: صفحه فعلی (1-based)
        total_pages: تعداد کل صفحات
    
    Returns:
        InlineKeyboardMarkup
    """
    keyboard = []
    
    # دکمه‌های صفحه قبل/بعد
    row = []
    
    if current_page > 1:
        row.append(InlineKeyboardButton(
            "⬅️ قبلی",
            callback_data=f"products_page:{current_page - 1}"
        ))
    
    # نمایش شماره صفحه
    row.append(InlineKeyboardButton(
        f"📄 {current_page}/{total_pages}",
        callback_data="page_info"
    ))
    
    if current_page < total_pages:
        row.append(InlineKeyboardButton(
            "➡️ بعدی",
            callback_data=f"products_page:{current_page + 1}"
        ))
    
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)
