"""
✅ FEATURE #1: Monitoring Dashboard
یه صفحه وب ساده برای چک کردن وضعیت بات
"""
import logging
from datetime import datetime
from flask import Flask, jsonify, render_template_string
import threading

logger = logging.getLogger(__name__)

# متغیرهای global برای آمار
bot_start_time = None
total_users = 0
total_orders = 0
pending_orders = 0
active_cart_users = 0
last_error = None
error_count = 0

app = Flask(__name__)

# HTML Template ساده
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Monitoring Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .header h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .status {
            display: inline-block;
            padding: 8px 20px;
            background: #10b981;
            color: white;
            border-radius: 25px;
            font-weight: bold;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .card h3 {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .card .value {
            color: #333;
            font-size: 2.5em;
            font-weight: bold;
        }
        .card .icon {
            font-size: 3em;
            margin-bottom: 10px;
        }
        .info-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 15px 0;
            border-bottom: 1px solid #eee;
        }
        .info-row:last-child {
            border-bottom: none;
        }
        .info-label {
            color: #666;
            font-weight: 600;
        }
        .info-value {
            color: #333;
            font-family: monospace;
        }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1em;
            cursor: pointer;
            margin-top: 20px;
        }
        .refresh-btn:hover {
            background: #5568d3;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .pulse {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Bot Monitoring Dashboard</h1>
            <span class="status pulse">● Running</span>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="icon">👥</div>
                <h3>Total Users</h3>
                <div class="value" id="total-users">-</div>
            </div>
            
            <div class="card">
                <div class="icon">📦</div>
                <h3>Total Orders</h3>
                <div class="value" id="total-orders">-</div>
            </div>
            
            <div class="card">
                <div class="icon">⏳</div>
                <h3>Pending Orders</h3>
                <div class="value" id="pending-orders">-</div>
            </div>
            
            <div class="card">
                <div class="icon">🛒</div>
                <h3>Active Carts</h3>
                <div class="value" id="active-carts">-</div>
            </div>
        </div>
        
        <div class="info-card">
            <h2 style="margin-bottom: 20px; color: #667eea;">📊 System Information</h2>
            
            <div class="info-row">
                <span class="info-label">Bot Status</span>
                <span class="info-value" style="color: #10b981;">✅ Running</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Uptime</span>
                <span class="info-value" id="uptime">-</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Start Time</span>
                <span class="info-value" id="start-time">-</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Last Error</span>
                <span class="info-value" id="last-error" style="color: #ef4444;">None</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Error Count</span>
                <span class="info-value" id="error-count">0</span>
            </div>
            
            <button class="refresh-btn" onclick="loadStats()">🔄 Refresh Data</button>
        </div>
    </div>
    
    <script>
        function loadStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('total-users').textContent = data.total_users || '-';
                    document.getElementById('total-orders').textContent = data.total_orders || '-';
                    document.getElementById('pending-orders').textContent = data.pending_orders || '-';
                    document.getElementById('active-carts').textContent = data.active_cart_users || '-';
                    document.getElementById('uptime').textContent = data.uptime || '-';
                    document.getElementById('start-time').textContent = data.start_time || '-';
                    document.getElementById('last-error').textContent = data.last_error || 'None';
                    document.getElementById('error-count').textContent = data.error_count || '0';
                })
                .catch(error => {
                    console.error('Error loading stats:', error);
                });
        }
        
        // بارگذاری اولیه
        loadStats();
        
        // بروزرسانی خودکار هر 10 ثانیه
        setInterval(loadStats, 10000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """صفحه اصلی داشبورد"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/health')
def health_check():
    """Health check endpoint ساده"""
    global bot_start_time
    
    if bot_start_time:
        uptime = str(datetime.now() - bot_start_time).split('.')[0]
    else:
        uptime = "Unknown"
    
    return jsonify({
        'status': 'running',
        'uptime': uptime,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/stats')
def get_stats():
    """API برای دریافت آمار کامل"""
    global bot_start_time, total_users, total_orders, pending_orders
    global active_cart_users, last_error, error_count
    
    if bot_start_time:
        uptime = str(datetime.now() - bot_start_time).split('.')[0]
        start_time_str = bot_start_time.strftime('%Y-%m-%d %H:%M:%S')
    else:
        uptime = "Unknown"
        start_time_str = "Unknown"
    
    return jsonify({
        'status': 'running',
        'uptime': uptime,
        'start_time': start_time_str,
        'total_users': total_users,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'active_cart_users': active_cart_users,
        'last_error': last_error,
        'error_count': error_count
    })


def update_stats(db, cart_locks_dict):
    """
    بروزرسانی آمار از دیتابیس
    این تابع از main.py صدا زده میشه
    """
    global total_users, total_orders, pending_orders, active_cart_users
    
    try:
        # تعداد کاربران
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # تعداد سفارشات
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        
        # سفارشات در انتظار
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status IN ('pending', 'waiting_payment')")
        pending_orders = cursor.fetchone()[0]
        
        # سبدهای فعال
        active_cart_users = len(cart_locks_dict)
        
    except Exception as e:
        logger.error(f"Error updating monitoring stats: {e}")


def set_error(error_message):
    """ثبت خطا"""
    global last_error, error_count
    last_error = str(error_message)[:100]  # محدود به 100 کاراکتر
    error_count += 1


def run_monitoring_server(port=5000, host='0.0.0.0'):
    """اجرای سرور monitoring در thread جداگانه"""
    global bot_start_time
    bot_start_time = datetime.now()
    
    logger.info(f"🌐 Starting monitoring dashboard on http://{host}:{port}")
    
    # غیرفعال کردن لاگ های Flask
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)
    
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Failed to start monitoring server: {e}")


def start_monitoring_dashboard(port=5000, host='0.0.0.0'):
    """
    شروع داشبورد monitoring
    این تابع از main.py صدا زده میشه
    """
    monitoring_thread = threading.Thread(
        target=run_monitoring_server,
        args=(port, host),
        daemon=True,
        name="MonitoringDashboard"
    )
    monitoring_thread.start()
    
    logger.info(f"✅ Monitoring dashboard started at http://{host}:{port}")
    logger.info(f"   - Dashboard: http://{host}:{port}/")
    logger.info(f"   - Health Check: http://{host}:{port}/health")
    logger.info(f"   - Stats API: http://{host}:{port}/api/stats")
    
    return monitoring_thread
