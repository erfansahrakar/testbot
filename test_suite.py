"""
Test Suite کامل برای ربات فروشگاه مانتو
✅ Coverage: validators, database, config, rate_limiter, states
✅ استفاده از pytest fixtures
✅ Mock کردن database و telegram
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

# ==================== Fixtures ====================

@pytest.fixture
def temp_db():
    """ایجاد دیتابیس موقت برای تست"""
    fd, path = tempfile.mkstemp(suffix='.db')
    yield path
    os.close(fd)
    os.unlink(path)


@pytest.fixture
def db(temp_db):
    """
    Database instance برای تست
    FIX: قبلاً patch کار نمی‌کرد چون DATABASE_NAME داخل DatabaseConnectionPool
    مستقیم استفاده میشه. الان مستقیم temp_db رو پاس میدیم.
    """
    from database import Database, DatabaseConnectionPool
    from unittest.mock import patch
    
    # patch روی محل واقعی استفاده (داخل database module)
    with patch('database.DATABASE_NAME', temp_db):
        db_instance = Database()
        yield db_instance
        db_instance.close()


@pytest.fixture
def mock_update():
    """Mock telegram Update"""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.message = Mock()
    update.callback_query = Mock()
    return update


@pytest.fixture
def mock_context():
    """Mock telegram Context"""
    context = Mock()
    context.bot_data = {'db': None}
    context.user_data = {}
    context.bot = AsyncMock()
    return context


# ==================== Tests: Validators ====================

class TestValidators:
    """تست اعتبارسنجی‌ها"""
    
    def test_validate_phone_valid(self):
        """تست شماره تلفن معتبر"""
        from validators import Validators
        
        valid, error = Validators.validate_phone("09123456789")
        assert valid is True
        assert error is None
    
    def test_validate_phone_invalid_length(self):
        """تست شماره با طول نامعتبر"""
        from validators import Validators
        
        valid, error = Validators.validate_phone("0912345678")
        assert valid is False
        assert "11 رقم" in error
    
    def test_validate_phone_invalid_format(self):
        """تست فرمت نامعتبر"""
        from validators import Validators
        
        valid, error = Validators.validate_phone("02123456789")
        assert valid is False
        assert "فرمت" in error
    
    def test_validate_price_valid(self):
        """تست قیمت معتبر"""
        from validators import Validators
        
        valid, error, price = Validators.validate_price("50000")
        assert valid is True
        assert error is None
        assert price == 50000.0
    
    def test_validate_price_with_comma(self):
        """تست قیمت با کاما"""
        from validators import Validators
        
        valid, error, price = Validators.validate_price("1,000,000")
        assert valid is True
        assert price == 1000000.0
    
    def test_validate_price_too_high(self):
        """تست قیمت بیش از حد"""
        from validators import Validators
        
        valid, error, price = Validators.validate_price("200000000")
        assert valid is False
        # چک کنیم که خطا داره (فرمت دقیق مهم نیست)
        assert error is not None
        assert "قیمت" in error
    
    def test_validate_price_negative(self):
        """تست قیمت منفی"""
        from validators import Validators
        
        valid, error, price = Validators.validate_price("-5000")
        assert valid is False
    
    def test_validate_quantity_valid(self):
        """تست تعداد معتبر"""
        from validators import Validators
        
        valid, error, qty = Validators.validate_quantity("10")
        assert valid is True
        assert qty == 10
    
    def test_validate_quantity_invalid(self):
        """تست تعداد نامعتبر"""
        from validators import Validators
        
        valid, error, qty = Validators.validate_quantity("abc")
        assert valid is False
        assert "عدد صحیح" in error
    
    def test_validate_discount_code_valid(self):
        """تست کد تخفیف معتبر"""
        from validators import Validators
        
        valid, error, code = Validators.validate_discount_code("SUMMER2024")
        assert valid is True
        assert code == "SUMMER2024"
    
    def test_validate_discount_code_too_short(self):
        """تست کد کوتاه"""
        from validators import Validators
        
        valid, error, code = Validators.validate_discount_code("AB")
        assert valid is False
        assert "3 کاراکتر" in error
    
    def test_validate_discount_code_invalid_chars(self):
        """تست کد با کاراکترهای نامعتبر"""
        from validators import Validators
        
        valid, error, code = Validators.validate_discount_code("TEST@123")
        assert valid is False
        assert "حروف و اعداد" in error
    
    def test_validate_name_valid(self):
        """تست نام معتبر"""
        from validators import Validators
        
        valid, error, name = Validators.validate_name("علی رضایی")
        assert valid is True
        assert name == "علی رضایی"
    
    def test_validate_name_too_short(self):
        """تست نام کوتاه"""
        from validators import Validators
        
        valid, error, name = Validators.validate_name("AB")
        assert valid is False
    
    def test_validate_address_valid(self):
        """تست آدرس معتبر"""
        from validators import Validators
        
        address = "تهران، خیابان ولیعصر، کوچه ۱۵"
        valid, error, cleaned = Validators.validate_address(address)
        assert valid is True
    
    def test_validate_address_too_short(self):
        """تست آدرس کوتاه"""
        from validators import Validators
        
        valid, error, cleaned = Validators.validate_address("تهران")
        assert valid is False
        assert "10 کاراکتر" in error
    
    def test_validate_percentage_valid(self):
        """تست درصد معتبر"""
        from validators import Validators
        
        valid, error = Validators.validate_percentage(50)
        assert valid is True
    
    def test_validate_percentage_invalid(self):
        """تست درصد نامعتبر"""
        from validators import Validators
        
        valid, error = Validators.validate_percentage(150)
        assert valid is False
        assert "0 تا 100" in error
    
    def test_safe_int(self):
        """تست تبدیل امن به int"""
        from validators import safe_int
        
        assert safe_int("123") == 123
        assert safe_int("1,234") == 1234
        assert safe_int("abc", default=0) == 0
    
    def test_safe_float(self):
        """تست تبدیل امن به float"""
        from validators import safe_float
        
        assert safe_float("123.45") == 123.45
        assert safe_float("1,234.56") == 1234.56
        assert safe_float("abc", default=0.0) == 0.0


# ==================== Tests: Database ====================

class TestDatabase:
    """تست عملیات دیتابیس"""
    
    def test_create_tables(self, db):
        """تست ایجاد جداول"""
        conn = db._get_conn()
        cursor = conn.cursor()
        
        # بررسی وجود جداول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'products' in tables
        assert 'packs' in tables
        assert 'users' in tables
        assert 'cart' in tables
        assert 'orders' in tables
        assert 'discount_codes' in tables
    
    def test_add_product(self, db):
        """تست افزودن محصول"""
        product_id = db.add_product("مانتو مشکی", "توضیحات", "photo_123")
        
        assert product_id > 0
        
        product = db.get_product(product_id)
        assert product is not None
        assert product[1] == "مانتو مشکی"
    
    def test_add_pack(self, db):
        """تست افزودن پک"""
        product_id = db.add_product("محصول تست", "توضیحات", "photo_123")
        pack_id = db.add_pack(product_id, "پک 6 تایی", 6, 300000)
        
        assert pack_id > 0
        
        pack = db.get_pack(pack_id)
        assert pack is not None
        assert pack[2] == "پک 6 تایی"
        assert pack[3] == 6
        assert pack[4] == 300000
    
    def test_get_packs(self, db):
        """تست دریافت پک‌های محصول"""
        product_id = db.add_product("محصول تست", "توضیحات", "photo_123")
        db.add_pack(product_id, "پک 1", 3, 150000)
        db.add_pack(product_id, "پک 2", 6, 280000)
        
        packs = db.get_packs(product_id)
        assert len(packs) == 2
    
    def test_add_user(self, db):
        """تست افزودن کاربر"""
        db.add_user(12345, "testuser", "Test User")
        
        user = db.get_user(12345)
        assert user is not None
        assert user[0] == 12345
        assert user[1] == "testuser"
    
    def test_update_user_info(self, db):
        """تست بروزرسانی اطلاعات کاربر"""
        db.add_user(12345, "testuser", "Test User")
        db.update_user_info(
            12345,
            phone="09123456789",
            address="تهران، خیابان ولیعصر",
            full_name="علی رضایی"
        )
        
        user = db.get_user(12345)
        assert user[4] == "09123456789"
        assert user[3] == "علی رضایی"
    
    def test_add_to_cart(self, db):
        """تست افزودن به سبد خرید"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک 6", 6, 300000)
        
        db.add_to_cart(12345, product_id, pack_id, quantity=1)
        
        cart = db.get_cart(12345)
        assert len(cart) > 0
        assert cart[0][5] == 6  # تعداد
    
    def test_add_to_cart_duplicate(self, db):
        """تست افزودن تکراری به سبد"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک 6", 6, 300000)
        
        db.add_to_cart(12345, product_id, pack_id, quantity=1)
        db.add_to_cart(12345, product_id, pack_id, quantity=1)
        
        cart = db.get_cart(12345)
        assert len(cart) == 1
        assert cart[0][5] == 12  # 6 + 6
    
    def test_clear_cart(self, db):
        """تست خالی کردن سبد"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک 6", 6, 300000)
        db.add_to_cart(12345, product_id, pack_id, quantity=1)
        
        db.clear_cart(12345)
        
        cart = db.get_cart(12345)
        assert len(cart) == 0
    
    def test_create_order(self, db):
        """تست ایجاد سفارش"""
        db.add_user(12345, "test", "Test")
        
        items = [
            {
                'product': 'محصول 1',
                'pack': 'پک 6',
                'quantity': 6,
                'price': 300000
            }
        ]
        
        order_id = db.create_order(
            user_id=12345,
            items=items,
            total_price=300000,
            discount_amount=0,
            final_price=300000
        )
        
        assert order_id > 0
        
        order = db.get_order(order_id)
        assert order is not None
        assert order[1] == 12345
    
    def test_create_discount(self, db):
        """تست ایجاد کد تخفیف"""
        discount_id = db.create_discount(
            code="SUMMER2024",
            type="percentage",
            value=10,
            min_purchase=100000
        )
        
        assert discount_id > 0
        
        discount = db.get_discount("SUMMER2024")
        assert discount is not None
        assert discount[2] == "percentage"
        assert discount[3] == 10
    
    def test_get_statistics(self, db):
        """تست دریافت آمار"""
        stats = db.get_statistics()
        
        assert 'total_orders' in stats
        assert 'total_users' in stats
        assert 'total_products' in stats
        assert stats['total_orders'] >= 0
    
    def test_cleanup_old_orders(self, db):
        """تست پاکسازی سفارشات قدیمی"""
        db.add_user(12345, "test", "Test")
        
        items = [{'product': 'تست', 'pack': 'تست', 'quantity': 1, 'price': 1000}]
        order_id = db.create_order(12345, items, 1000, 0, 1000)
        
        # تغییر وضعیت به rejected
        db.update_order_status(order_id, 'rejected')
        
        # تغییر تاریخ به قدیمی
        conn = db._get_conn()
        cursor = conn.cursor()
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        cursor.execute(
            "UPDATE orders SET created_at = ? WHERE id = ?",
            (old_date, order_id)
        )
        conn.commit()
        
        # پاکسازی
        report = db.cleanup_old_orders(days_old=7)
        
        assert report['success'] is True
        assert report['deleted_count'] >= 1
    
    def test_delete_product_cascade(self, db):
        """تست حذف محصول با cascade"""
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک", 6, 300000)
        
        db.delete_product(product_id)
        
        # بررسی حذف شدن محصول و پک
        product = db.get_product(product_id)
        pack = db.get_pack(pack_id)
        
        assert product is None
        assert pack is None


# ==================== Tests: Config ====================

class TestConfig:
    """تست تنظیمات"""
    
    def test_button_texts(self):
        """تست متن دکمه‌ها"""
        from config import BUTTON_TEXTS, get_button_text
        
        assert 'CART' in BUTTON_TEXTS
        assert get_button_text('CART') == '🛒 سبد خرید'
    
    def test_shipping_methods(self):
        """تست روش‌های ارسال"""
        from config import SHIPPING_METHODS, get_shipping_display
        
        assert 'terminal' in SHIPPING_METHODS
        assert get_shipping_display('terminal') == 'ترمینال 🚌'
    
    def test_order_status_display(self):
        """تست نمایش وضعیت سفارش"""
        from config import get_order_status_display
        
        emoji, text = get_order_status_display('pending')
        assert emoji == '⏳'
        assert 'انتظار' in text
    
    def test_limits(self):
        """تست محدودیت‌ها"""
        from config import LIMITS
        
        assert LIMITS['MAX_PRICE'] == 100_000_000
        assert LIMITS['RATE_LIMIT_REQUESTS'] == 20


# ==================== Tests: States ====================

class TestStates:
    """تست State ها"""
    
    def test_order_status_enum(self):
        """تست OrderStatus Enum"""
        from states import OrderStatus
        
        assert OrderStatus.PENDING == 'pending'
        assert OrderStatus.CONFIRMED == 'confirmed'
        assert str(OrderStatus.PENDING) == 'pending'
    
    def test_conversation_states(self):
        """تست Conversation States"""
        from states import PRODUCT_NAME, PRODUCT_DESC, PRODUCT_PHOTO
        
        assert isinstance(PRODUCT_NAME, int)
        assert isinstance(PRODUCT_DESC, int)
        assert PRODUCT_NAME != PRODUCT_DESC


# ==================== Tests: Rate Limiter ====================

class TestRateLimiter:
    """تست محدودیت درخواست"""
    
    def test_check_rate_limit_allowed(self):
        """تست درخواست مجاز"""
        from rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        allowed, remaining, show_alert = limiter.check_rate_limit(
            user_id=12345,
            max_requests=10,
            window_seconds=60
        )
        
        assert allowed is True
        assert remaining == 0
    
    def test_check_rate_limit_exceeded(self):
        """تست محدودیت درخواست"""
        from rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        # ارسال 11 درخواست (بیشتر از حد)
        for _ in range(11):
            allowed, remaining, show_alert = limiter.check_rate_limit(
                user_id=12345,
                max_requests=10,
                window_seconds=60
            )
        
        assert allowed is False
        assert remaining > 0
    
    def test_check_action_limit(self):
        """تست محدودیت عملیات"""
        from rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        allowed, remaining, show_alert = limiter.check_action_limit(
            user_id=12345,
            action='order',
            max_requests=3,
            window_seconds=3600
        )
        
        assert allowed is True
    
    def test_reset_user(self):
        """تست ریست محدودیت کاربر"""
        from rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        # ایجاد محدودیت
        for _ in range(11):
            limiter.check_rate_limit(12345, 10, 60)
        
        # ریست
        limiter.reset_user(12345)
        
        # چک مجاز بودن
        allowed, _, _ = limiter.check_rate_limit(12345, 10, 60)
        assert allowed is True
    
    def test_get_stats(self):
        """تست دریافت آمار"""
        from rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        limiter.check_rate_limit(12345, 10, 60)
        
        stats = limiter.get_stats(12345)
        
        assert stats['user_id'] == 12345
        assert 'general_requests' in stats


# ==================== Tests: Edge Cases ====================

class TestEdgeCases:
    """تست موارد خاص و Edge Cases"""
    
    def test_validate_phone_with_spaces(self):
        """تست شماره با فاصله"""
        from validators import Validators
        
        valid, error = Validators.validate_phone("0912 345 6789")
        assert valid is True
    
    def test_validate_price_empty(self):
        """تست قیمت خالی"""
        from validators import Validators
        
        valid, error, price = Validators.validate_price("")
        assert valid is False
    
    def test_validate_quantity_zero(self):
        """تست تعداد صفر"""
        from validators import Validators
        
        valid, error, qty = Validators.validate_quantity("0")
        assert valid is False
    
    def test_db_transaction_rollback(self, db):
        """تست Rollback در Transaction"""
        try:
            with db.transaction() as cursor:
                cursor.execute("INSERT INTO products (name) VALUES (?)", ("تست",))
                raise Exception("Test rollback")
        except:
            pass
        
        # بررسی عدم ذخیره
        products = db.get_all_products()
        assert len(products) == 0
    
    def test_cart_with_deleted_product(self, db):
        """تست سبد با محصول حذف شده"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک", 6, 300000)
        
        db.add_to_cart(12345, product_id, pack_id, 1)
        db.delete_product(product_id)
        
        # سبد باید خالی باشه (cascade delete)
        cart = db.get_cart(12345)
        assert len(cart) == 0
    
    def test_expired_order(self, db):
        """تست سفارش منقضی شده"""
        db.add_user(12345, "test", "Test")
        items = [{'product': 'تست', 'pack': 'تست', 'quantity': 1, 'price': 1000}]
        order_id = db.create_order(12345, items, 1000, 0, 1000)
        
        # تغییر تاریخ انقضا به گذشته
        conn = db._get_conn()
        cursor = conn.cursor()
        past_date = (datetime.now() - timedelta(days=2)).isoformat()
        cursor.execute(
            "UPDATE orders SET expires_at = ? WHERE id = ?",
            (past_date, order_id)
        )
        conn.commit()
        
        # چک کردن منقضی بودن
        order = db.get_order(order_id)
        expires_at = order[11]
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        is_expired = datetime.now() > expires_at
        assert is_expired is True


# ==================== Tests: Performance ====================

class TestPerformance:
    """تست عملکرد"""
    
    def test_bulk_cart_operations(self, db):
        """تست عملیات انبوه سبد"""
        import time
        
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        
        # افزودن 100 پک
        pack_ids = []
        for i in range(100):
            pack_id = db.add_pack(product_id, f"پک {i}", 6, 300000)
            pack_ids.append(pack_id)
        
        # افزودن به سبد
        start = time.time()
        for pack_id in pack_ids[:50]:
            db.add_to_cart(12345, product_id, pack_id, 1)
        duration = time.time() - start
        
        # باید کمتر از 1 ثانیه باشه
        assert duration < 1.0
    
    def test_query_performance(self, db):
        """تست سرعت Query"""
        import time
        
        # افزودن 100 محصول
        for i in range(100):
            db.add_product(f"محصول {i}", "توضیحات", "photo")
        
        # تست سرعت Query
        start = time.time()
        products = db.get_all_products()
        duration = time.time() - start
        
        assert len(products) == 100
        assert duration < 0.5  # کمتر از نیم ثانیه


# ==================== Tests: Discount ====================

class TestDiscount:
    """تست عملیات تخفیف"""
    
    def test_create_discount_percentage(self, db):
        """تست ایجاد تخفیف درصدی"""
        discount_id = db.create_discount(
            code="TEST10",
            type="percentage",
            value=10,
            min_purchase=0
        )
        
        assert discount_id > 0
        
        discount = db.get_discount("TEST10")
        assert discount is not None
        assert discount[2] == "percentage"
        assert discount[3] == 10
    
    def test_create_discount_fixed(self, db):
        """تست ایجاد تخفیف ثابت"""
        discount_id = db.create_discount(
            code="FIXED50K",
            type="fixed",
            value=50000,
            min_purchase=0
        )
        
        discount = db.get_discount("FIXED50K")
        assert discount[2] == "fixed"
        assert discount[3] == 50000
    
    def test_discount_with_limits(self, db):
        """تست تخفیف با محدودیت‌ها"""
        discount_id = db.create_discount(
            code="LIMITED",
            type="percentage",
            value=20,
            min_purchase=100000,
            max_discount=50000,
            usage_limit=10
        )
        
        discount = db.get_discount("LIMITED")
        assert discount[4] == 100000  # min_purchase
        assert discount[5] == 50000   # max_discount
        assert discount[6] == 10      # usage_limit
    
    def test_toggle_discount(self, db):
        """تست فعال/غیرفعال کردن تخفیف"""
        discount_id = db.create_discount(
            code="TOGGLE",
            type="percentage",
            value=10,
            min_purchase=0
        )
        
        # چک فعال بودن
        discount = db.get_discount("TOGGLE")
        assert discount[10] == 1  # is_active
        
        # غیرفعال کردن
        db.toggle_discount(discount_id)
        
        # چک غیرفعال شدن
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM discount_codes WHERE id = ?", (discount_id,))
        is_active = cursor.fetchone()[0]
        assert is_active == 0
    
    def test_delete_discount(self, db):
        """تست حذف تخفیف"""
        discount_id = db.create_discount(
            code="DELETE_ME",
            type="percentage",
            value=10,
            min_purchase=0
        )
        
        db.delete_discount(discount_id)
        
        discount = db.get_discount("DELETE_ME")
        assert discount is None
    
    def test_use_discount(self, db):
        """تست استفاده از تخفیف"""
        db.add_user(12345, "test", "Test")
        
        discount_id = db.create_discount(
            code="USE_ME",
            type="percentage",
            value=10,
            min_purchase=0
        )
        
        items = [{'product': 'تست', 'pack': 'تست', 'quantity': 1, 'price': 1000}]
        order_id = db.create_order(12345, items, 1000, 100, 900, "USE_ME")
        
        db.use_discount(12345, "USE_ME", order_id)
        
        # چک افزایش used_count
        discount = db.get_discount("USE_ME")
        assert discount[7] == 1  # used_count


# ==================== Tests: Order Management ====================

class TestOrderManagement:
    """تست مدیریت سفارشات"""
    
    def test_order_items_json(self, db):
        """تست ذخیره و بازیابی JSON"""
        db.add_user(12345, "test", "Test")
        
        items = [
            {
                'product': 'مانتو مشکی',
                'pack': 'پک 6 تایی',
                'quantity': 6,
                'price': 300000,
                'admin_notes': 'رنگ مشکی'
            }
        ]
        
        order_id = db.create_order(12345, items, 300000, 0, 300000)
        order = db.get_order(order_id)
        
        import json
        retrieved_items = json.loads(order[2])
        
        assert len(retrieved_items) == 1
        assert retrieved_items[0]['admin_notes'] == 'رنگ مشکی'
    
    def test_order_status_transitions(self, db):
        """تست تغییر وضعیت سفارش"""
        from states import OrderStatus
        
        db.add_user(12345, "test", "Test")
        items = [{'product': 'تست', 'pack': 'تست', 'quantity': 1, 'price': 1000}]
        order_id = db.create_order(12345, items, 1000, 0, 1000)
        
        # pending -> waiting_payment
        db.update_order_status(order_id, OrderStatus.WAITING_PAYMENT)
        order = db.get_order(order_id)
        assert order[7] == OrderStatus.WAITING_PAYMENT
        
        # waiting_payment -> payment_confirmed
        db.update_order_status(order_id, OrderStatus.PAYMENT_CONFIRMED)
        order = db.get_order(order_id)
        assert order[7] == OrderStatus.PAYMENT_CONFIRMED
    
    def test_user_orders_filter(self, db):
        """تست فیلتر سفارشات کاربر"""
        from states import OrderStatus
        
        db.add_user(12345, "test", "Test")
        items = [{'product': 'تست', 'pack': 'تست', 'quantity': 1, 'price': 1000}]
        
        # سفارش تایید شده
        order1 = db.create_order(12345, items, 1000, 0, 1000)
        db.update_order_status(order1, OrderStatus.CONFIRMED)
        
        # سفارش رد شده
        order2 = db.create_order(12345, items, 1000, 0, 1000)
        db.update_order_status(order2, OrderStatus.REJECTED)
        
        # سفارش منقضی
        order3 = db.create_order(12345, items, 1000, 0, 1000)
        conn = db._get_conn()
        cursor = conn.cursor()
        past = (datetime.now() - timedelta(days=2)).isoformat()
        cursor.execute("UPDATE orders SET expires_at = ? WHERE id = ?", (past, order3))
        conn.commit()
        
        # فقط سفارش confirmed باید برگرده
        orders = db.get_user_orders(12345)
        order_ids = [o[0] for o in orders]
        
        assert order1 in order_ids
        assert order2 not in order_ids


# ==================== Tests: Integration ====================

class TestIntegration:
    """تست‌های یکپارچگی"""
    
    def test_full_order_flow(self, db):
        """تست جریان کامل سفارش"""
        # 1. ثبت کاربر
        db.add_user(12345, "test", "Test User")
        db.update_user_info(
            12345,
            phone="09123456789",
            address="تهران، خیابان ولیعصر",
            full_name="علی رضایی"
        )
        
        # 2. افزودن محصول و پک
        product_id = db.add_product("مانتو مشکی", "زیبا و شیک", "photo_123")
        pack_id = db.add_pack(product_id, "پک 6 تایی", 6, 300000)
        
        # 3. افزودن به سبد
        db.add_to_cart(12345, product_id, pack_id, 1)
        cart = db.get_cart(12345)
        assert len(cart) == 1
        
        # 4. اعمال تخفیف
        db.create_discount("SUMMER", "percentage", 10, 0)
        discount = db.get_discount("SUMMER")
        assert discount is not None
        
        # 5. ثبت سفارش
        items = [{'product': 'مانتو', 'pack': 'پک 6', 'quantity': 6, 'price': 300000}]
        order_id = db.create_order(12345, items, 300000, 30000, 270000, "SUMMER")
        
        # 6. چک سفارش
        order = db.get_order(order_id)
        assert order[5] == 270000  # final_price
        assert order[6] == "SUMMER"  # discount_code
        
        # 7. خالی کردن سبد
        db.clear_cart(12345)
        cart = db.get_cart(12345)
        assert len(cart) == 0
    
    def test_concurrent_cart_operations(self, db):
        """تست عملیات همزمان سبد"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک", 6, 300000)
        
        # افزودن همزمان
        for _ in range(5):
            db.add_to_cart(12345, product_id, pack_id, 1)
        
        cart = db.get_cart(12345)
        # باید 30 تا باشه (5 * 6)
        assert cart[0][5] == 30


# ==================== Tests: Security ====================

class TestSecurity:
    """تست امنیت"""
    
    def test_sql_injection_product_name(self, db):
        """تست SQL Injection در نام محصول"""
        malicious_name = "'; DROP TABLE products; --"
        
        product_id = db.add_product(malicious_name, "توضیحات", "photo")
        
        # باید بدون خطا ذخیره بشه
        product = db.get_product(product_id)
        assert product is not None
        
        # جدول نباید حذف شده باشه
        products = db.get_all_products()
        assert len(products) > 0
    
    def test_sql_injection_discount_code(self, db):
        """تست SQL Injection در کد تخفیف"""
        malicious_code = "' OR '1'='1"
        
        discount = db.get_discount(malicious_code)
        # نباید چیزی پیدا کنه
        assert discount is None
    
    def test_xss_in_product_description(self, db):
        """تست XSS در توضیحات"""
        xss_desc = "<script>alert('XSS')</script>"
        
        product_id = db.add_product("محصول", xss_desc, "photo")
        product = db.get_product(product_id)
        
        # باید ذخیره بشه (sanitization در frontend)
        assert product[2] == xss_desc


# ==================== Tests: Data Integrity ====================

class TestDataIntegrity:
    """تست یکپارچگی داده‌ها"""
    
    def test_unique_discount_code(self, db):
        """تست یکتا بودن کد تخفیف"""
        db.create_discount("UNIQUE", "percentage", 10, 0)
        
        # تلاش برای افزودن دوباره
        with pytest.raises(Exception):
            db.create_discount("UNIQUE", "percentage", 20, 0)
    
    def test_foreign_key_constraint(self, db):
        """تست محدودیت Foreign Key"""
        # تلاش برای افزودن پک به محصول نامعتبر
        with pytest.raises(Exception):
            db.add_pack(99999, "پک", 6, 300000)
    
    def test_cart_unique_constraint(self, db):
        """تست محدودیت UNIQUE در سبد"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        pack_id = db.add_pack(product_id, "پک", 6, 300000)
        
        # افزودن دوباره باید quantity رو زیاد کنه نه آیتم جدید
        db.add_to_cart(12345, product_id, pack_id, 1)
        db.add_to_cart(12345, product_id, pack_id, 1)
        
        cart = db.get_cart(12345)
        assert len(cart) == 1  # فقط یک آیتم


# ==================== Tests: Stress Testing ====================

class TestStress:
    """تست استرس و حجم بالا"""
    
    def test_many_products(self, db):
        """تست تعداد زیاد محصول"""
        for i in range(1000):
            db.add_product(f"محصول {i}", "توضیحات", "photo")
        
        products = db.get_all_products()
        assert len(products) == 1000
    
    def test_large_cart(self, db):
        """تست سبد بزرگ"""
        db.add_user(12345, "test", "Test")
        product_id = db.add_product("محصول", "توضیحات", "photo")
        
        # 100 پک مختلف
        for i in range(100):
            pack_id = db.add_pack(product_id, f"پک {i}", 6, 300000)
            db.add_to_cart(12345, product_id, pack_id, 1)
        
        cart = db.get_cart(12345)
        assert len(cart) == 100
    
    def test_long_text_fields(self, db):
        """تست فیلدهای متنی بلند"""
        long_desc = "توضیحات " * 1000  # خیلی بلند
        long_address = "آدرس " * 100
        
        product_id = db.add_product("محصول", long_desc, "photo")
        db.add_user(12345, "test", "Test")
        db.update_user_info(12345, address=long_address[:500])  # max 500
        
        product = db.get_product(product_id)
        user = db.get_user(12345)
        
        assert product is not None
        assert user[6] is not None


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--cov=.", "--cov-report=term"])
