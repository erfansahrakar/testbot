"""
تعریف State های مکالمه برای ConversationHandler ها
✅ FIX: OrderStatus از enums.py import میشه (یک منبع واحد)
"""
from enum import Enum

# FIX: OrderStatus از enums ایمپورت میشه تا یک تعریف واحد داشته باشیم
# (قبلاً دو تا تعریف موازی در states.py و enums.py بود)
from enums import OrderStatus


# ==================== Conversation States ====================

# State های محصول و پک (ادمین)
PRODUCT_NAME, PRODUCT_DESC, PRODUCT_PHOTO = range(3)
PACK_NAME, PACK_QUANTITY, PACK_PRICE = range(3, 6)

# State های اطلاعات کاربر
FULL_NAME, ADDRESS_TEXT, PHONE_NUMBER = range(6, 9)

# State های ویرایش محصول
EDIT_PRODUCT_NAME, EDIT_PRODUCT_DESC, EDIT_PRODUCT_PHOTO = range(9, 12)

# State های ویرایش پک
EDIT_PACK_NAME, EDIT_PACK_QUANTITY, EDIT_PACK_PRICE = range(12, 15)

# State های تخفیف
DISCOUNT_CODE, DISCOUNT_TYPE, DISCOUNT_VALUE = range(15, 18)
DISCOUNT_MIN_PURCHASE, DISCOUNT_MAX, DISCOUNT_LIMIT = range(18, 21)
DISCOUNT_PER_USER_LIMIT = 21
DISCOUNT_START, DISCOUNT_END = range(22, 24)

# State پیام دسته‌جمعی
BROADCAST_MESSAGE = 24

# 🆕 State برای وارد کردن کد تخفیف توسط کاربر
ENTER_DISCOUNT_CODE = 25

# 🆕 State برای ویرایش تعداد آیتم توسط ادمین
EDIT_ITEM_QUANTITY = 26
