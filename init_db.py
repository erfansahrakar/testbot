#!/usr/bin/env python3
"""
فایل راه‌اندازی و تست دیتابیس
این فایل را یک بار اجرا کنید تا دیتابیس بررسی و مقداردهی شود
"""

from database import Database

def main():
    print("🔄 در حال راه‌اندازی دیتابیس...")
    
    try:
        # ایجاد instance دیتابیس
        db = Database()
        
        print("✅ دیتابیس با موفقیت راه‌اندازی شد!")
        print("\n📊 اطلاعات دیتابیس:")
        print("=" * 50)
        
        # تست و نمایش آمار
        products = db.get_all_products()
        print(f"📦 تعداد محصولات: {len(products)}")
        
        users = db.get_all_users()
        print(f"👥 تعداد کاربران: {len(users)}")
        
        stats = db.get_statistics()
        print(f"🛒 تعداد سفارشات: {stats.get('total_orders', 0)}")
        print(f"💰 درآمد کل: {stats.get('total_income', 0):,.0f} تومان")
        
        # تست connection
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            print("\n✅ تست اتصال دیتابیس موفق بود!")
        else:
            print("\n❌ تست اتصال دیتابیس ناموفق!")
        
        print("=" * 50)
        print("✅ همه چیز آماده است!")
        
    except Exception as e:
        print(f"\n❌ خطا در راه‌اندازی دیتابیس: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
