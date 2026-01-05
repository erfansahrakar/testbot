"""
سیستم Health Check برای نظارت بر سلامت ربات
✅ وضعیت دیتابیس
✅ مصرف RAM و CPU
✅ آمار کاربران و سفارشات
✅ آخرین خطاها
"""
import psutil
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """وضعیت سلامت سیستم"""
    status: str  # "healthy", "warning", "critical"
    timestamp: str
    uptime_seconds: float
    database: Dict
    memory: Dict
    cpu: Dict
    users: Dict
    orders: Dict
    errors: List[Dict]
    
    def to_dict(self):
        return asdict(self)


class HealthChecker:
    """کلاس مدیریت Health Check"""
    
    def __init__(self, db, start_time: float):
        self.db = db
        self.start_time = start_time
        self.last_errors: List[Dict] = []
        self.max_errors = 50  # نگهداری آخرین 50 خطا
    
    def add_error(self, error_type: str, error_message: str, user_id: Optional[int] = None):
        """اضافه کردن خطا به لیست"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message,
            'user_id': user_id
        }
        
        self.last_errors.append(error_entry)
        
        # نگهداری فقط آخرین خطاها
        if len(self.last_errors) > self.max_errors:
            self.last_errors = self.last_errors[-self.max_errors:]
    
    def check_database(self) -> Dict:
        """بررسی وضعیت دیتابیس"""
        try:
            # تست اتصال
            self.db.cursor.execute("SELECT 1")
            
            # اندازه دیتابیس
            from config import DATABASE_NAME
            db_size = os.path.getsize(DATABASE_NAME) / (1024 * 1024)  # MB
            
            # تعداد جداول
            self.db.cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            )
            table_count = self.db.cursor.fetchone()[0]
            
            return {
                'status': 'connected',
                'size_mb': round(db_size, 2),
                'tables': table_count,
                'healthy': True
            }
        except Exception as e:
            logger.error(f"❌ Database health check failed: {e}")
            return {
                'status': 'disconnected',
                'error': str(e),
                'healthy': False
            }
    
    def check_memory(self) -> Dict:
        """بررسی مصرف حافظه"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            # مصرف RAM
            ram_used_mb = memory_info.rss / (1024 * 1024)
            
            # مصرف کل سیستم
            system_memory = psutil.virtual_memory()
            
            # وضعیت
            if ram_used_mb > 500:
                status = 'critical'
                healthy = False
            elif ram_used_mb > 300:
                status = 'warning'
                healthy = True
            else:
                status = 'good'
                healthy = True
            
            return {
                'process_mb': round(ram_used_mb, 2),
                'system_percent': system_memory.percent,
                'system_available_mb': round(system_memory.available / (1024 * 1024), 2),
                'status': status,
                'healthy': healthy
            }
        except Exception as e:
            logger.error(f"❌ Memory health check failed: {e}")
            return {
                'error': str(e),
                'healthy': False
            }
    
    def check_cpu(self) -> Dict:
        """بررسی مصرف CPU"""
        try:
            process = psutil.Process(os.getpid())
            
            # CPU درصد
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # تعداد threadها
            num_threads = process.num_threads()
            
            # وضعیت
            if cpu_percent > 80:
                status = 'critical'
                healthy = False
            elif cpu_percent > 50:
                status = 'warning'
                healthy = True
            else:
                status = 'good'
                healthy = True
            
            return {
                'percent': round(cpu_percent, 2),
                'threads': num_threads,
                'status': status,
                'healthy': healthy
            }
        except Exception as e:
            logger.error(f"❌ CPU health check failed: {e}")
            return {
                'error': str(e),
                'healthy': False
            }
    
    def check_users(self) -> Dict:
        """بررسی آمار کاربران"""
        try:
            # کل کاربران
            self.db.cursor.execute("SELECT COUNT(*) FROM users")
            total_users = self.db.cursor.fetchone()[0]
            
            # کاربران امروز
            self.db.cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_users = self.db.cursor.fetchone()[0]
            
            # کاربران این هفته
            self.db.cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE created_at >= DATE('now', '-7 days')
            """)
            week_users = self.db.cursor.fetchone()[0]
            
            return {
                'total': total_users,
                'today': today_users,
                'this_week': week_users,
                'healthy': True
            }
        except Exception as e:
            logger.error(f"❌ Users health check failed: {e}")
            return {
                'error': str(e),
                'healthy': False
            }
    
    def check_orders(self) -> Dict:
        """بررسی آمار سفارشات"""
        try:
            # کل سفارشات
            self.db.cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = self.db.cursor.fetchone()[0]
            
            # سفارشات امروز
            self.db.cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_orders = self.db.cursor.fetchone()[0]
            
            # سفارشات pending
            self.db.cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'pending'
            """)
            pending_orders = self.db.cursor.fetchone()[0]
            
            # سفارشات موفق امروز
            self.db.cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
            """)
            successful_today = self.db.cursor.fetchone()[0]
            
            return {
                'total': total_orders,
                'today': today_orders,
                'pending': pending_orders,
                'successful_today': successful_today,
                'healthy': True
            }
        except Exception as e:
            logger.error(f"❌ Orders health check failed: {e}")
            return {
                'error': str(e),
                'healthy': False
            }
    
    def get_health_status(self) -> HealthStatus:
        """دریافت وضعیت کامل سلامت"""
        # محاسبه uptime
        uptime = time.time() - self.start_time
        
        # بررسی تمام سیستم‌ها
        db_status = self.check_database()
        memory_status = self.check_memory()
        cpu_status = self.check_cpu()
        users_status = self.check_users()
        orders_status = self.check_orders()
        
        # تعیین وضعیت کلی
        all_healthy = all([
            db_status.get('healthy', False),
            memory_status.get('healthy', False),
            cpu_status.get('healthy', False),
            users_status.get('healthy', False),
            orders_status.get('healthy', False)
        ])
        
        has_warning = (
            memory_status.get('status') == 'warning' or
            cpu_status.get('status') == 'warning'
        )
        
        if not all_healthy:
            overall_status = 'critical'
        elif has_warning:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        return HealthStatus(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            uptime_seconds=round(uptime, 2),
            database=db_status,
            memory=memory_status,
            cpu=cpu_status,
            users=users_status,
            orders=orders_status,
            errors=self.last_errors[-10:]  # آخرین 10 خطا
        )
    
    def get_health_report(self) -> str:
        """گزارش متنی وضعیت سلامت"""
        status = self.get_health_status()
        
        # ایموجی وضعیت
        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'critical': '🔴'
        }
        
        emoji = status_emoji.get(status.status, '❓')
        
        # محاسبه uptime به فرمت خوانا
        uptime_hours = status.uptime_seconds / 3600
        if uptime_hours < 1:
            uptime_str = f"{status.uptime_seconds / 60:.1f} دقیقه"
        elif uptime_hours < 24:
            uptime_str = f"{uptime_hours:.1f} ساعت"
        else:
            uptime_str = f"{uptime_hours / 24:.1f} روز"
        
        report = f"{emoji} **وضعیت سیستم: {status.status.upper()}**\n\n"
        report += f"⏱ Uptime: {uptime_str}\n"
        report += f"📅 {status.timestamp[:16]}\n\n"
        
        # دیتابیس
        report += "**💾 دیتابیس:**\n"
        if status.database.get('healthy'):
            report += f"✅ متصل - حجم: {status.database['size_mb']} MB\n"
            report += f"📊 جداول: {status.database['tables']}\n"
        else:
            report += f"❌ خطا: {status.database.get('error', 'Unknown')}\n"
        report += "\n"
        
        # حافظه
        report += "**🧠 حافظه:**\n"
        if status.memory.get('healthy') is not False:
            mem_status = status.memory.get('status', 'unknown')
            mem_emoji = '✅' if mem_status == 'good' else '⚠️'
            report += f"{mem_emoji} استفاده: {status.memory['process_mb']} MB\n"
            report += f"💻 سیستم: {status.memory['system_percent']}%\n"
        else:
            report += f"❌ خطا: {status.memory.get('error', 'Unknown')}\n"
        report += "\n"
        
        # CPU
        report += "**⚡ CPU:**\n"
        if status.cpu.get('healthy') is not False:
            cpu_status = status.cpu.get('status', 'unknown')
            cpu_emoji = '✅' if cpu_status == 'good' else '⚠️'
            report += f"{cpu_emoji} استفاده: {status.cpu['percent']}%\n"
            report += f"🔀 Threads: {status.cpu['threads']}\n"
        else:
            report += f"❌ خطا: {status.cpu.get('error', 'Unknown')}\n"
        report += "\n"
        
        # کاربران
        report += "**👥 کاربران:**\n"
        if status.users.get('healthy'):
            report += f"📊 کل: {status.users['total']}\n"
            report += f"🆕 امروز: {status.users['today']}\n"
            report += f"📈 این هفته: {status.users['this_week']}\n"
        else:
            report += f"❌ خطا: {status.users.get('error', 'Unknown')}\n"
        report += "\n"
        
        # سفارشات
        report += "**📦 سفارشات:**\n"
        if status.orders.get('healthy'):
            report += f"📊 کل: {status.orders['total']}\n"
            report += f"🆕 امروز: {status.orders['today']}\n"
            report += f"⏳ در انتظار: {status.orders['pending']}\n"
            report += f"✅ موفق امروز: {status.orders['successful_today']}\n"
        else:
            report += f"❌ خطا: {status.orders.get('error', 'Unknown')}\n"
        report += "\n"
        
        # خطاها
        if status.errors:
            report += f"**⚠️ آخرین خطاها:** ({len(status.errors)})\n"
            for err in status.errors[-5:]:
                report += f"• {err['type']}: {err['message'][:50]}...\n"
        else:
            report += "**✅ خطایی ثبت نشده**\n"
        
        return report


# ==================== Helper Functions ====================

def format_bytes(bytes_value: float) -> str:
    """فرمت کردن byte به واحد خوانا"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


def format_uptime(seconds: float) -> str:
    """فرمت کردن uptime"""
    if seconds < 60:
        return f"{seconds:.0f} ثانیه"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} دقیقه"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f} ساعت"
    else:
        return f"{seconds / 86400:.1f} روز"
