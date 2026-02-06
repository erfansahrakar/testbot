"""
اسکریپت Migration برای به‌روزرسانی دیتابیس
✅ اضافه کردن Indexes
✅ اضافه کردن ستون‌های جدید
✅ پاکسازی داده‌های قدیمی

استفاده:
    python migrate_database.py
"""
import sqlite3
import logging
import sys
from datetime import datetime
from config import DATABASE_NAME

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_backup():
    """ایجاد بکاپ قبل از migration"""
    import shutil
    
    backup_name = f"{DATABASE_NAME}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        shutil.copy2(DATABASE_NAME, backup_name)
        logger.info(f"✅ بکاپ ایجاد شد: {backup_name}")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد بکاپ: {e}")
        return False


def add_indexes(cursor):
    """اضافه کردن Indexes برای بهبود Performance"""
    logger.info("📊 اضافه کردن Indexes...")
    
    indexes = [
        ("idx_orders_user_id", "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)"),
        ("idx_orders_status", "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"),
        ("idx_orders_created_at", "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)"),
        ("idx_cart_user_id", "CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id)"),
        ("idx_discount_code", "CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code)"),
        ("idx_products_channel_msg", "CREATE INDEX IF NOT EXISTS idx_products_channel_msg ON products(channel_message_id)"),
        ("idx_packs_product_id", "CREATE INDEX IF NOT EXISTS idx_packs_product_id ON packs(product_id)"),
        ("idx_orders_status_created", "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC)"),
    ]
    
    created_count = 0
    for name, sql in indexes:
        try:
            cursor.execute(sql)
            logger.info(f"  ✅ {name}")
            created_count += 1
        except sqlite3.Error as e:
            logger.warning(f"  ⚠️ {name}: {e}")
    
    logger.info(f"✅ {created_count}/{len(indexes)} Index اضافه شد")


def add_missing_columns(cursor):
    """اضافه کردن ستون‌های جدید"""
    logger.info("📋 بررسی ستون‌های جدید...")
    
    # چک کردن ستون per_user_limit در discount_codes
    cursor.execute("PRAGMA table_info(discount_codes)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'per_user_limit' not in columns:
        logger.info("  🔄 اضافه کردن per_user_limit...")
        cursor.execute("ALTER TABLE discount_codes ADD COLUMN per_user_limit INTEGER")
        logger.info("  ✅ per_user_limit اضافه شد")
    else:
        logger.info("  ℹ️ per_user_limit قبلاً وجود دارد")
    
    # چک کردن ستون expires_at در orders
    cursor.execute("PRAGMA table_info(orders)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'expires_at' not in columns:
        logger.info("  🔄 اضافه کردن expires_at...")
        cursor.execute("ALTER TABLE orders ADD COLUMN expires_at TIMESTAMP")
        logger.info("  ✅ expires_at اضافه شد")
    else:
        logger.info("  ℹ️ expires_at قبلاً وجود دارد")


def cleanup_old_data(cursor, days_old=30):
    """پاکسازی داده‌های قدیمی"""
    logger.info(f"🧹 پاکسازی داده‌های قدیمی‌تر از {days_old} روز...")
    
    try:
        # حذف سفارشات رد شده قدیمی
        cursor.execute("""
            DELETE FROM orders 
            WHERE status = 'rejected' 
            AND datetime(created_at) < datetime('now', '-' || ? || ' days')
        """, (days_old,))
        
        rejected_count = cursor.rowcount
        
        # حذف سفارشات منقضی شده
        cursor.execute("""
            DELETE FROM orders 
            WHERE status = 'expired' 
            AND datetime(created_at) < datetime('now', '-' || ? || ' days')
        """, (days_old,))
        
        expired_count = cursor.rowcount
        
        logger.info(f"  ✅ {rejected_count} سفارش رد شده حذف شد")
        logger.info(f"  ✅ {expired_count} سفارش منقضی شده حذف شد")
        
        return rejected_count + expired_count
    
    except Exception as e:
        logger.error(f"  ❌ خطا در پاکسازی: {e}")
        return 0


def get_database_stats(cursor):
    """دریافت آمار دیتابیس"""
    logger.info("📊 آمار دیتابیس:")
    
    stats = {}
    
    # تعداد محصولات
    cursor.execute("SELECT COUNT(*) FROM products")
    stats['products'] = cursor.fetchone()[0]
    logger.info(f"  • محصولات: {stats['products']:,}")
    
    # تعداد پک‌ها
    cursor.execute("SELECT COUNT(*) FROM packs")
    stats['packs'] = cursor.fetchone()[0]
    logger.info(f"  • پک‌ها: {stats['packs']:,}")
    
    # تعداد کاربران
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['users'] = cursor.fetchone()[0]
    logger.info(f"  • کاربران: {stats['users']:,}")
    
    # تعداد سفارشات
    cursor.execute("SELECT COUNT(*) FROM orders")
    stats['orders'] = cursor.fetchone()[0]
    logger.info(f"  • سفارشات: {stats['orders']:,}")
    
    # سفارشات در انتظار
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    stats['pending_orders'] = cursor.fetchone()[0]
    logger.info(f"  • سفارشات در انتظار: {stats['pending_orders']:,}")
    
    # تعداد کدهای تخفیف
    cursor.execute("SELECT COUNT(*) FROM discount_codes")
    stats['discounts'] = cursor.fetchone()[0]
    logger.info(f"  • کدهای تخفیف: {stats['discounts']:,}")
    
    # اندازه دیتابیس
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    size_bytes = cursor.fetchone()[0]
    size_mb = size_bytes / (1024 * 1024)
    logger.info(f"  • حجم دیتابیس: {size_mb:.2f} MB")
    
    return stats


def optimize_database(conn):
    """بهینه‌سازی دیتابیس"""
    logger.info("⚡ بهینه‌سازی دیتابیس...")
    
    try:
        # VACUUM برای بازیابی فضا
        conn.execute("VACUUM")
        logger.info("  ✅ VACUUM انجام شد")
        
        # ANALYZE برای بهبود Query Planner
        conn.execute("ANALYZE")
        logger.info("  ✅ ANALYZE انجام شد")
        
        return True
    except Exception as e:
        logger.error(f"  ❌ خطا در بهینه‌سازی: {e}")
        return False


def migrate_database():
    """اجرای کامل Migration"""
    logger.info("="*60)
    logger.info("🚀 شروع Migration دیتابیس")
    logger.info("="*60)
    
    # ایجاد بکاپ
    if not create_backup():
        response = input("⚠️ بکاپ ایجاد نشد! ادامه می‌دهید؟ (yes/no): ")
        if response.lower() != 'yes':
            logger.info("❌ Migration لغو شد")
            return False
    
    conn = None
    try:
        # اتصال به دیتابیس
        logger.info(f"🔌 اتصال به {DATABASE_NAME}...")
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # فعال کردن Foreign Keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # شروع Transaction
        cursor.execute("BEGIN")
        
        # اضافه کردن Indexes
        add_indexes(cursor)
        
        # اضافه کردن ستون‌های جدید
        add_missing_columns(cursor)
        
        # Commit تغییرات
        conn.commit()
        logger.info("✅ تغییرات commit شد")
        
        # پاکسازی داده‌های قدیمی (اختیاری)
        response = input("\n🧹 پاکسازی داده‌های قدیمی؟ (yes/no): ")
        if response.lower() == 'yes':
            cursor.execute("BEGIN")
            deleted = cleanup_old_data(cursor, days_old=30)
            conn.commit()
            logger.info(f"✅ {deleted} رکورد قدیمی حذف شد")
        
        # بهینه‌سازی
        response = input("\n⚡ بهینه‌سازی دیتابیس؟ (yes/no): ")
        if response.lower() == 'yes':
            optimize_database(conn)
        
        # نمایش آمار
        print("\n" + "="*60)
        get_database_stats(cursor)
        print("="*60)
        
        logger.info("\n✅ Migration با موفقیت تکمیل شد!")
        return True
    
    except Exception as e:
        logger.error(f"\n❌ خطا در Migration: {e}")
        if conn:
            conn.rollback()
            logger.info("↩️ تغییرات Rollback شد")
        return False
    
    finally:
        if conn:
            conn.close()
            logger.info("🔌 اتصال به دیتابیس بسته شد")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("📦 Database Migration Script")
    print("="*60)
    print(f"Database: {DATABASE_NAME}")
    print("="*60 + "\n")
    
    response = input("⚠️ آیا مطمئن هستید؟ (yes/no): ")
    
    if response.lower() == 'yes':
        success = migrate_database()
        sys.exit(0 if success else 1)
    else:
        logger.info("❌ Migration لغو شد")
        sys.exit(0)
