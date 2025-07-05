#!/usr/bin/python3
"""
Smart Car Park System - Web Interface (最终修复版)
"""

import sqlite3
import logging
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify
import time
import os
import functools
from datetime import datetime, timedelta
import pytz  # 添加时区支持

# 全局变量，存储系统实例
car_park_system = None
db_lock = threading.Lock()  # 数据库访问锁
system_start_time = datetime.now()  # 系统启动时间

# 创建 Flask 应用
app = Flask(__name__)
app.secret_key = os.urandom(24)

# 设置数据库路径（使用绝对路径）
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'car_park.db')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_app.log"),
        logging.StreamHandler()
    ]
)

# 默认管理员凭据
ADMIN_USERNAME = "fct777"
ADMIN_PASSWORD = "fct777"

# 设置本地时区（例如北京时间）
LOCAL_TIMEZONE = pytz.timezone('Asia/Shanghai')

# 修改所有数据库访问函数，添加锁机制
def execute_db_query(query, params=(), fetch=False):
    """线程安全的数据库查询"""
    with db_lock:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # 设置行工厂为Row
            cursor = conn.cursor()
            cursor.execute(query, params)

            if fetch:
                result = cursor.fetchall()
                # 将Row对象转换为字典列表
                return [dict(row) for row in result]
            else:
                conn.commit()
                return None

        except Exception as e:
            logging.error(f"Database error: {str(e)}")
            return None
        finally:
            conn.close()

# 时间转换函数（UTC转本地时间）
def utc_to_local(utc_dt):
    """将UTC时间转换为本地时间"""
    if utc_dt is None:
        return None
    try:
        # 如果已经是带时区的时间，直接转换
        if utc_dt.tzinfo is not None:
            return utc_dt.astimezone(LOCAL_TIMEZONE)
        # 如果是naive时间，先设置为UTC再转换
        return pytz.utc.localize(utc_dt).astimezone(LOCAL_TIMEZONE)
    except Exception as e:
        logging.error(f"Time conversion error: {str(e)}")
        return utc_dt

# 添加上下文处理器，提供 'now' 给所有模板
@app.context_processor
def inject_now():
    return {'now': datetime.now().astimezone(LOCAL_TIMEZONE)}

# 登录装饰器
def login_required(func):
    @functools.wraps(func)
    def secure_function(*args, **kwargs):
        if "logged_in" not in session:
            flash("请登录以访问页面", "danger")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return secure_function

@app.route("/")
def index():
    """首页 - 如果未登录则重定向到登录页，否则到仪表盘"""
    if "logged_in" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """登录页"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # 简单认证
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            flash("登录成功", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("用户名或密码错误", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    """登出并重定向到登录页"""
    session.pop("logged_in", None)
    flash("您已成功退出登录", "info")
    return redirect(url_for("login"))



@app.route('/plate_update_stream')
@login_required
def plate_update_stream():
    """SSE流，用于通知前端车牌更新"""
    def event_stream():
        while True:
            if car_park_system:
                # 等待更新事件
                car_park_system.update_event.wait()
                yield "data: update\n\n"
            time.sleep(0.1)

    return Response(event_stream(), mimetype='text/event-stream')

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        # 获取注册车牌数量
        count_result = execute_db_query("SELECT COUNT(*) as count FROM plates", fetch=True)
        plate_count = count_result[0]['count'] if count_result and count_result[0] else 0

        # 获取今日进入车辆数
        today = datetime.now().astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d")
        today_entries = execute_db_query(
            "SELECT COUNT(*) as count FROM movement_log WHERE action='ACCESS_GRANTED' AND DATE(timestamp)=?",
            (today,),
            fetch=True
        )
        today_count = today_entries[0]['count'] if today_entries and today_entries[0] else 0

        # 获取最近活动
        recent_activity = execute_db_query(
            "SELECT plate_number, action, timestamp FROM movement_log ORDER BY timestamp DESC LIMIT 5",
            fetch=True
        ) or []
        
        # 转换时间为本地时区
        for entry in recent_activity:
            entry['timestamp'] = utc_to_local(datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S')).strftime('%Y-%m-%d %H:%M:%S')

        return render_template(
            "dashboard.html",
            plate_count=plate_count,
            today_entries=today_count,
            recent_activity=recent_activity
        )
    except Exception as e:
        logging.error(f"Dashboard error: {str(e)}")
        flash("加载时出错", "danger")
        return render_template("dashboard.html", error=True)

@app.route("/plates")
@login_required
def list_plates():
    """列出所有注册的车牌"""
    try:
        plates = execute_db_query(
            "SELECT id, plate_number, added_date FROM plates ORDER BY added_date DESC",
            fetch=True
        ) or []  # 确保总是返回列表
        
        # 转换时间为本地时区
        for plate in plates:
            plate['added_date'] = utc_to_local(datetime.strptime(plate['added_date'], '%Y-%m-%d %H:%M:%S')).strftime('%Y-%m-%d %H:%M:%S')

        logging.info(f"Found {len(plates)} plates in database")
        return render_template("plates.html", plates=plates)
    except Exception as e:
        logging.error(f"Error listing plates: {str(e)}", exc_info=True)
        flash("获取车牌数据失败", "danger")
        return render_template("plates.html", plates=[])

@app.route("/plates/add", methods=["GET", "POST"])
@login_required
def add_plate():
    """添加新车牌"""
    if request.method == "POST":
        plate_number = request.form.get("plate_number", "").strip().upper()

        if not plate_number:
            flash("车牌号码不能为空", "danger")
            return redirect(url_for("add_plate"))

        try:
            # 检查车牌是否已存在
            existing = execute_db_query(
                "SELECT 1 FROM plates WHERE plate_number = ?",
                (plate_number,),
                fetch=True
            )

            if existing:
                flash(f"车牌 {plate_number}已经存在", "warning")
                return redirect(url_for("list_plates"))

            # 添加新车牌
            execute_db_query(
                "INSERT INTO plates (plate_number) VALUES (?)",
                (plate_number,)
            )

            flash(f"车牌 {plate_number} 添加成功", "success")
            return redirect(url_for("list_plates"))

        except Exception as e:
            logging.error(f"Error adding plate: {str(e)}")
            flash("添加车牌失败", "danger")
            return redirect(url_for("add_plate"))

    return render_template("add_plate.html")

@app.route("/plates/remove/<int:plate_id>", methods=["POST"])
@login_required
def remove_plate(plate_id):
    """移除车牌"""
    try:
        # 获取车牌号
        plate = execute_db_query(
            "SELECT plate_number FROM plates WHERE id = ?",
            (plate_id,),
            fetch=True
        )

        if plate:
            plate_number = plate[0]['plate_number']

            # 删除车牌
            execute_db_query(
                "DELETE FROM plates WHERE id = ?",
                (plate_id,)
            )

            flash(f"车牌 {plate_number} 已成功移除", "success")
        else:
            flash("车牌不存在", "danger")

        return redirect(url_for("list_plates"))

    except Exception as e:
        logging.error(f"Error removing plate: {str(e)}")
        flash("删除车牌失败", "danger")
        return redirect(url_for("list_plates"))

@app.route("/logs")
@login_required
def view_logs():
    """查看车辆移动日志"""
    try:
        logs = execute_db_query(
            "SELECT id, plate_number, action, timestamp FROM movement_log ORDER BY timestamp DESC LIMIT 100",
            fetch=True
        ) or []
        
        # 转换时间为本地时区
        for log in logs:
            log['timestamp'] = utc_to_local(datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S')).strftime('%Y-%m-%d %H:%M:%S')

        return render_template("logs.html", logs=logs)
    except Exception as e:
        logging.error(f"Error viewing logs: {str(e)}")
        flash("获取日志数据失败", "danger")
        return render_template("logs.html", logs=[])

@app.route('/video_feed')
@login_required
def video_feed():
    def generate():
        while True:
            if car_park_system:
                frame = car_park_system.get_current_frame()
                if frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.05)  # 约20FPS

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def set_car_park_system(system):
    global car_park_system
    car_park_system = system
    logging.info("Car park system instance set in web interface")

@app.route('/plate_image')
@login_required
def plate_image():
    """获取处理后的车牌图像"""
    if car_park_system:
        plate_img, _ = car_park_system.get_processed_data()
        if plate_img:
            return Response(plate_img, mimetype='image/jpeg')
    # 返回空图像
    return Response(b'', mimetype='image/jpeg')

@app.route('/plate_text')
@login_required
def plate_text():
    """获取识别的车牌文本和时间戳"""
    if car_park_system:
        _, plate_text = car_park_system.get_processed_data()
        last_time = car_park_system.last_process_time
        # 使用本地时区显示时间
        timestamp = datetime.fromtimestamp(last_time).astimezone(LOCAL_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S') if last_time > 0 else "从未更新"
        return jsonify({
            "text": plate_text or "未识别到车牌",
            "timestamp": timestamp
        })
    return jsonify({"text": "系统未初始化", "timestamp": "N/A"})


@app.route('/add_plate_from_monitor', methods=['POST'])
@login_required
def add_plate_from_monitor():
    """从监控页面添加车牌到数据库"""
    if not car_park_system:
        return jsonify({"success": False, "message": "系统未初始化"})

    # 获取当前识别的车牌
    _, plate_text = car_park_system.get_processed_data()

    if not plate_text or plate_text in ["等待识别", "未检测到车牌", "系统未初始化"]:
        return jsonify({"success": False, "message": "没有有效的车牌信息"})

    try:
        # 检查车牌是否已存在
        existing = execute_db_query(
            "SELECT 1 FROM plates WHERE plate_number = ?",
            (plate_text,),
            fetch=True
        )

        if existing:
            return jsonify({"success": False, "message": f"车牌 {plate_text} 已存在"})

        # 添加新车牌
        execute_db_query(
            "INSERT INTO plates (plate_number) VALUES (?)",
            (plate_text,)
        )

        return jsonify({
            "success": True,
            "message": f"车牌 {plate_text} 添加成功",
            "plate": plate_text
        })
    except Exception as e:
        logging.error(f"Error adding plate from monitor: {str(e)}")
        return jsonify({"success": False, "message": "添加车牌失败"})



@app.route('/system_stats')
@login_required
def system_stats():
    """获取系统统计数据"""
    try:
        # 获取注册车牌数量
        count_result = execute_db_query("SELECT COUNT(*) as count FROM plates", fetch=True)
        plate_count = count_result[0]['count'] if count_result and count_result[0] else 0

        # 获取今日进入车辆数
        today = datetime.now().astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d")
        today_entries = execute_db_query(
            "SELECT COUNT(*) as count FROM movement_log WHERE action='ACCESS_GRANTED' AND DATE(timestamp)=?",
            (today,),
            fetch=True
        )
        today_count = today_entries[0]['count'] if today_entries and today_entries[0] else 0

        # 计算系统运行时间
        uptime = datetime.now() - system_start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

        # 计算识别准确率
        accuracy = car_park_system.get_recognition_accuracy() if car_park_system else 92

        return jsonify({
            "plate_count": plate_count,
            "today_entries": today_count,
            "uptime": uptime_str,
            "accuracy": accuracy
        })
    except Exception as e:
        logging.error(f"Error getting system stats: {str(e)}")
        return jsonify({
            "plate_count": 0,
            "today_entries": 0,
            "uptime": "00:00:00",
            "accuracy": 0
        })

@app.route('/monitor')
@login_required
def monitor():
    """系统监控页面，显示视频流和处理结果"""
    try:
        return render_template('monitor.html')
    except Exception as e:
        logging.error(f"Error rendering monitor page: {str(e)}", exc_info=True)
        return render_template("500.html"), 500

# 添加手动触发检测的路由
@app.route('/trigger_detection')
@login_required
def trigger_detection():
    """手动触发车牌检测"""
    if car_park_system:
        try:
            # 在后台线程中触发检测
            def run_detection():
                car_park_system.force_plate_detection()

            threading.Thread(target=run_detection).start()
            flash("车牌检测已手动触发", "success")
        except Exception as e:
            logging.error(f"Error triggering detection: {str(e)}")
            flash("触发检测失败", "danger")
    else:
        flash("系统未初始化", "danger")

    return redirect(url_for('monitor'))

@app.errorhandler(404)
def page_not_found(e):
    """处理404错误"""
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    """处理500错误"""
    logging.error(f"Server error: {str(e)}")
    return render_template("500.html"), 500

if __name__ == "__main__":
    # 确保数据库存在
    if not os.path.exists(db_path):
        try:
            # 创建车牌表
            execute_db_query('''
                CREATE TABLE IF NOT EXISTS plates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT UNIQUE NOT NULL,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建日志表
            execute_db_query('''
                CREATE TABLE IF NOT EXISTS movement_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_number TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            logging.info("Database initialized")

        except Exception as e:
            logging.error(f"Failed to initialize database: {str(e)}")

    # 运行Flask应用
    app.run(host="0.0.0.0", port=5000, debug=True)