"""
✅ FEATURE #4: Export Manager
دانلود گزارشات به صورت Excel/CSV
"""
import logging
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import json
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID

logger = logging.getLogger(__name__)


class ExportManager:
    """مدیریت export گزارشات"""
    
    def __init__(self, db):
        self.db = db
    
    def _style_header(self, ws):
        """استایل دادن به header"""
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
    
    def _auto_width(self, ws):
        """تنظیم خودکار عرض ستون‌ها"""
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    def export_orders(self, start_date=None, end_date=None, status=None):
        """
        Export سفارشات به Excel
        
        Args:
            start_date: تاریخ شروع (datetime)
            end_date: تاریخ پایان (datetime)
            status: فیلتر وضعیت (str)
        
        Returns:
            str: مسیر فایل ایجاد شده
        """
        try:
            # دریافت سفارشات
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            query = "SELECT * FROM orders WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND created_at >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND created_at <= ?"
                params.append(end_date.isoformat())
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            orders = cursor.fetchall()
            
            # ساخت Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "سفارشات"
            
            # Header
            headers = [
                "شماره سفارش",
                "کاربر ID",
                "نام کاربر",
                "محصولات",
                "قیمت کل",
                "تخفیف",
                "قیمت نهایی",
                "کد تخفیف",
                "وضعیت",
                "نحوه ارسال",
                "تاریخ ثبت",
                "موبایل"
            ]
            ws.append(headers)
            
            # داده‌ها
            for order in orders:
                order_id, user_id, items_json, total_price, discount_amount, final_price, discount_code, status, receipt, shipping_method, created_at, expires_at, *rest = order
                
                # دریافت اطلاعات کاربر
                user = self.db.get_user(user_id)
                user_name = user[3] if user and len(user) > 3 and user[3] else "نامشخص"
                user_phone = user[4] if user and len(user) > 4 and user[4] else "ندارد"
                
                # پردازش آیتم‌ها
                items = json.loads(items_json)
                items_text = ", ".join([f"{item['product']} ({item['quantity']})" for item in items])
                
                # فرمت تاریخ
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = created_at.strftime('%Y-%m-%d %H:%M') if created_at else "نامشخص"
                
                # افزودن ردیف
                ws.append([
                    order_id,
                    user_id,
                    user_name,
                    items_text,
                    total_price,
                    discount_amount,
                    final_price,
                    discount_code or "-",
                    status,
                    shipping_method or "-",
                    date_str,
                    user_phone
                ])
            
            # استایل
            self._style_header(ws)
            self._auto_width(ws)
            
            # ذخیره فایل
            filename = f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = f"/home/claude/{filename}"
            wb.save(filepath)
            
            logger.info(f"✅ Exported {len(orders)} orders to {filename}")
            return filepath
        
        except Exception as e:
            logger.error(f"❌ Error exporting orders: {e}")
            raise
    
    def export_products(self):
        """Export محصولات به Excel"""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.id, p.name, p.description, 
                       COUNT(DISTINCT pk.id) as pack_count,
                       p.created_at
                FROM products p
                LEFT JOIN packs pk ON pk.product_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """)
            products = cursor.fetchall()
            
            # ساخت Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "محصولات"
            
            # Header
            headers = ["ID", "نام محصول", "توضیحات", "تعداد پک‌ها", "تاریخ ایجاد"]
            ws.append(headers)
            
            # داده‌ها
            for product in products:
                prod_id, name, desc, pack_count, created_at = product
                
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = created_at.strftime('%Y-%m-%d') if created_at else "نامشخص"
                
                ws.append([
                    prod_id,
                    name,
                    desc or "-",
                    pack_count,
                    date_str
                ])
            
            # استایل
            self._style_header(ws)
            self._auto_width(ws)
            
            # ذخیره
            filename = f"products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = f"/home/claude/{filename}"
            wb.save(filepath)
            
            logger.info(f"✅ Exported {len(products)} products to {filename}")
            return filepath
        
        except Exception as e:
            logger.error(f"❌ Error exporting products: {e}")
            raise
    
    def export_users(self):
        """Export کاربران به Excel"""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT u.id, u.username, u.full_name, u.phone, 
                       COUNT(DISTINCT o.id) as order_count,
                       SUM(CASE WHEN o.status IN ('confirmed', 'payment_confirmed') THEN o.final_price ELSE 0 END) as total_spent,
                       u.joined_at
                FROM users u
                LEFT JOIN orders o ON o.user_id = u.id
                GROUP BY u.id
                ORDER BY total_spent DESC
            """)
            users = cursor.fetchall()
            
            # ساخت Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "کاربران"
            
            # Header
            headers = ["User ID", "Username", "نام", "موبایل", "تعداد سفارش", "جمع خرید", "تاریخ عضویت"]
            ws.append(headers)
            
            # داده‌ها
            for user in users:
                user_id, username, full_name, phone, order_count, total_spent, joined_at = user
                
                if isinstance(joined_at, str):
                    joined_at = datetime.fromisoformat(joined_at.replace('Z', '+00:00'))
                date_str = joined_at.strftime('%Y-%m-%d') if joined_at else "نامشخص"
                
                ws.append([
                    user_id,
                    username or "-",
                    full_name or "-",
                    phone or "-",
                    order_count or 0,
                    total_spent or 0,
                    date_str
                ])
            
            # استایل
            self._style_header(ws)
            self._auto_width(ws)
            
            # ذخیره
            filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = f"/home/claude/{filename}"
            wb.save(filepath)
            
            logger.info(f"✅ Exported {len(users)} users to {filename}")
            return filepath
        
        except Exception as e:
            logger.error(f"❌ Error exporting users: {e}")
            raise
    
    def export_sales_report(self, period='month'):
        """
        گزارش فروش
        
        Args:
            period: 'week', 'month', 'year'
        """
        try:
            # محاسبه بازه زمانی
            now = datetime.now()
            
            if period == 'week':
                start_date = now - timedelta(days=7)
                title = "هفته اخیر"
            elif period == 'month':
                start_date = now - timedelta(days=30)
                title = "ماه اخیر"
            else:  # year
                start_date = now - timedelta(days=365)
                title = "سال اخیر"
            
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            # آمار کلی
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(final_price) as total_revenue,
                    AVG(final_price) as avg_order_value,
                    SUM(discount_amount) as total_discounts
                FROM orders
                WHERE created_at >= ? AND status IN ('confirmed', 'payment_confirmed')
            """, (start_date.isoformat(),))
            
            stats = cursor.fetchone()
            
            # ساخت Workbook
            wb = Workbook()
            
            # Sheet 1: خلاصه
            ws_summary = wb.active
            ws_summary.title = "خلاصه"
            
            ws_summary.append(["گزارش فروش", title])
            ws_summary.append([])
            ws_summary.append(["شاخص", "مقدار"])
            ws_summary.append(["تعداد سفارشات", stats[0] or 0])
            ws_summary.append(["جمع فروش", f"{stats[1] or 0:,} تومان"])
            ws_summary.append(["میانگین سفارش", f"{stats[2] or 0:,.0f} تومان"])
            ws_summary.append(["تخفیفات داده شده", f"{stats[3] or 0:,} تومان"])
            
            self._style_header(ws_summary)
            self._auto_width(ws_summary)
            
            # Sheet 2: محصولات پرفروش
            ws_products = wb.create_sheet("محصولات پرفروش")
            
            cursor.execute("""
                SELECT 
                    p.name,
                    COUNT(*) as sales_count,
                    SUM(json_extract(value, '$.quantity')) as total_quantity,
                    SUM(json_extract(value, '$.price')) as total_revenue
                FROM orders o, json_each(o.items) as je
                JOIN packs pk ON pk.id = json_extract(je.value, '$.pack_id')
                JOIN products p ON p.id = pk.product_id
                WHERE o.created_at >= ? AND o.status IN ('confirmed', 'payment_confirmed')
                GROUP BY p.id
                ORDER BY total_revenue DESC
                LIMIT 10
            """, (start_date.isoformat(),))
            
            top_products = cursor.fetchall()
            
            ws_products.append(["محصول", "تعداد فروش", "مجموع تعداد", "درآمد"])
            for product in top_products:
                ws_products.append(list(product))
            
            self._style_header(ws_products)
            self._auto_width(ws_products)
            
            # ذخیره
            filename = f"sales_report_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = f"/home/claude/{filename}"
            wb.save(filepath)
            
            logger.info(f"✅ Generated sales report: {filename}")
            return filepath
        
        except Exception as e:
            logger.error(f"❌ Error generating sales report: {e}")
            raise


# ==================== Handler Functions ====================

async def export_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی export"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [InlineKeyboardButton("📦 سفارشات", callback_data="export:orders")],
        [InlineKeyboardButton("📦 محصولات", callback_data="export:products")],
        [InlineKeyboardButton("👥 کاربران", callback_data="export:users")],
        [InlineKeyboardButton("📊 گزارش فروش (هفته)", callback_data="export:sales_week")],
        [InlineKeyboardButton("📊 گزارش فروش (ماه)", callback_data="export:sales_month")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_admin")]
    ]
    
    await update.message.reply_text(
        "📥 **دانلود گزارشات**\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش export"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    export_type = query.data.split(':')[1]
    
    await query.message.reply_text("⏳ در حال آماده‌سازی فایل...")
    
    try:
        db = context.bot_data['db']
        exporter = ExportManager(db)
        
        if export_type == 'orders':
            filepath = exporter.export_orders()
        elif export_type == 'products':
            filepath = exporter.export_products()
        elif export_type == 'users':
            filepath = exporter.export_users()
        elif export_type == 'sales_week':
            filepath = exporter.export_sales_report('week')
        elif export_type == 'sales_month':
            filepath = exporter.export_sales_report('month')
        else:
            await query.message.reply_text("❌ نوع export نامعتبر است!")
            return
        
        # ارسال فایل
        with open(filepath, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filepath.split('/')[-1],
                caption="✅ فایل آماده شد!"
            )
        
        # حذف فایل موقت
        import os
        os.remove(filepath)
        
    except Exception as e:
        logger.error(f"Error in export: {e}")
        await query.message.reply_text(f"❌ خطا در ساخت فایل: {str(e)}")
