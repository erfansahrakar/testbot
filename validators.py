"""
اعتبارسنجی ورودی‌های کاربر
🔒 امنیت: جلوگیری از ورودی‌های مخرب و نامعتبر
✅ CLEANED: کدهای unused حذف شد
✅ FIX: Max price 100 میلیون
✅ FIX: sanitize_input حذف شد (prepared statements کافیه)
"""
import re
from datetime import datetime
from typing import Tuple, Optional


class ValidationError(Exception):
    """خطای اعتبارسنجی"""
    pass


class Validators:
    """کلاس اعتبارسنجی ورودی‌ها"""
    
    # الگوهای Regex
    PHONE_PATTERN = re.compile(r'^09\d{9}$')
    ENGLISH_PERSIAN_PATTERN = re.compile(r'^[\u0600-\u06FFa-zA-Z\s]+$')
    ALPHANUMERIC_PATTERN = re.compile(r'^[a-zA-Z0-9]+$')
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
        """
        اعتبارسنجی شماره تلفن همراه
        
        مثال:
            >>> Validators.validate_phone("09123456789")
            (True, None)
        """
        if not phone:
            return False, "❌ شماره تلفن نمی‌تواند خالی باشد"
        
        # حذف فاصله و خط تیره
        phone = phone.replace(" ", "").replace("-", "")
        
        # بررسی طول
        if len(phone) != 11:
            return False, "❌ شماره تلفن باید 11 رقم باشد"
        
        # بررسی فرمت
        if not Validators.PHONE_PATTERN.match(phone):
            return False, "❌ فرمت شماره نادرست است\nمثال صحیح: 09123456789"
        
        return True, None
    
    @staticmethod
    def validate_price(price: str, min_value: float = 0, max_value: float = 100_000_000) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        اعتبارسنجی قیمت
        ✅ FIX: max_value به 100 میلیون تومان
        """
        if not price:
            return False, "❌ قیمت نمی‌تواند خالی باشد", None
        
        # حذف کاما و فاصله
        price = price.replace(",", "").replace(" ", "")
        
        try:
            price_float = float(price)
        except ValueError:
            return False, "❌ قیمت باید عدد باشد", None
        
        if price_float < min_value:
            return False, f"❌ قیمت باید حداقل {min_value:,.0f} تومان باشد", None
        
        if price_float > max_value:
            return False, f"❌ قیمت نمی‌تواند بیشتر از {max_value:,.0f} تومان باشد", None
        
        return True, None, price_float
    
    @staticmethod
    def validate_quantity(quantity: str, min_value: int = 1, max_value: int = 10000) -> Tuple[bool, Optional[str], Optional[int]]:
        """اعتبارسنجی تعداد"""
        if not quantity:
            return False, "❌ تعداد نمی‌تواند خالی باشد", None
        
        quantity = quantity.replace(",", "").replace(" ", "")
        
        try:
            qty_int = int(quantity)
        except ValueError:
            return False, "❌ تعداد باید عدد صحیح باشد", None
        
        if qty_int < min_value:
            return False, f"❌ تعداد باید حداقل {min_value} باشد", None
        
        if qty_int > max_value:
            return False, f"❌ تعداد نمی‌تواند بیشتر از {max_value:,} باشد", None
        
        return True, None, qty_int
    
    @staticmethod
    def validate_discount_code(code: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """اعتبارسنجی کد تخفیف"""
        if not code:
            return False, "❌ کد تخفیف نمی‌تواند خالی باشد", None
        
        code = code.strip().upper()
        
        if len(code) < 3:
            return False, "❌ کد تخفیف باید حداقل 3 کاراکتر باشد", None
        
        if len(code) > 20:
            return False, "❌ کد تخفیف نمی‌تواند بیشتر از 20 کاراکتر باشد", None
        
        if not Validators.ALPHANUMERIC_PATTERN.match(code):
            return False, "❌ کد تخفیف فقط می‌تواند شامل حروف و اعداد انگلیسی باشد", None
        
        return True, None, code
    
    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """اعتبارسنجی تاریخ (YYYY-MM-DD)"""
        if not date_str or date_str == "0":
            return True, None, None  # تاریخ اختیاری
        
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return False, "❌ فرمت تاریخ نادرست است\nفرمت صحیح: YYYY-MM-DD\nمثال: 2024-12-31", None
        
        # بررسی تاریخ منطقی
        min_date = datetime(2020, 1, 1)
        max_date = datetime(2030, 12, 31)
        
        if parsed_date < min_date or parsed_date > max_date:
            return False, "❌ تاریخ باید بین 2020 تا 2030 باشد", None
        
        return True, None, parsed_date
    
    @staticmethod
    def validate_name(name: str, min_length: int = 3, max_length: int = 100) -> Tuple[bool, Optional[str], Optional[str]]:
        """اعتبارسنجی نام"""
        if not name:
            return False, "❌ نام نمی‌تواند خالی باشد", None
        
        # حذف فاصله‌های اضافی
        name = " ".join(name.split())
        
        if len(name) < min_length:
            return False, f"❌ نام باید حداقل {min_length} کاراکتر باشد", None
        
        if len(name) > max_length:
            return False, f"❌ نام نمی‌تواند بیشتر از {max_length} کاراکتر باشد", None
        
        if not Validators.ENGLISH_PERSIAN_PATTERN.match(name):
            return False, "❌ نام فقط می‌تواند شامل حروف فارسی یا انگلیسی باشد", None
        
        return True, None, name
    
    @staticmethod
    def validate_address(address: str, min_length: int = 10, max_length: int = 500) -> Tuple[bool, Optional[str], Optional[str]]:
        """اعتبارسنجی آدرس"""
        if not address:
            return False, "❌ آدرس نمی‌تواند خالی باشد", None
        
        address = " ".join(address.split())
        
        if len(address) < min_length:
            return False, f"❌ آدرس باید حداقل {min_length} کاراکتر باشد\n\nلطفاً آدرس کامل (شهر، خیابان، کوچه، پلاک) را وارد کنید", None
        
        if len(address) > max_length:
            return False, f"❌ آدرس نمی‌تواند بیشتر از {max_length} کاراکتر باشد", None
        
        return True, None, address
    
    @staticmethod
    def validate_percentage(value: float) -> Tuple[bool, Optional[str]]:
        """اعتبارسنجی درصد (0-100)"""
        if value < 0 or value > 100:
            return False, "❌ درصد تخفیف باید بین 0 تا 100 باشد"
        return True, None
    
    @staticmethod
    def validate_product_name(name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """اعتبارسنجی نام محصول"""
        return Validators.validate_name(name, min_length=2, max_length=100)
    
    @staticmethod
    def validate_pack_name(name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """اعتبارسنجی نام پک"""
        if not name:
            return False, "❌ نام پک نمی‌تواند خالی باشد", None
        
        name = " ".join(name.split())
        
        if len(name) < 2:
            return False, "❌ نام پک باید حداقل 2 کاراکتر باشد", None
        
        if len(name) > 50:
            return False, "❌ نام پک نمی‌تواند بیشتر از 50 کاراکتر باشد", None
        
        return True, None, name


# ==================== Helper Functions ====================

def safe_int(value: str, default: int = 0) -> int:
    """تبدیل ایمن به int"""
    try:
        return int(value.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return default


def safe_float(value: str, default: float = 0.0) -> float:
    """تبدیل ایمن به float"""
    try:
        return float(value.replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return default


# ✅ REMOVED: sanitize_input
# دلیل: استفاده از prepared statements کافیه
# همیشه از prepared statements استفاده کنید:
# ✅ cursor.execute("INSERT INTO t (c) VALUES (?)", (value,))
# ❌ cursor.execute(f"INSERT INTO t (c) VALUES ('{value}')")
