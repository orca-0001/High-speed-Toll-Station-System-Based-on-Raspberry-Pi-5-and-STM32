#!/usr/bin/env python3
import time
import logging
import sqlite3
import serial
import cv2
import numpy as np
from io import BytesIO
import threading
import os
import sys
import re
from datetime import datetime
from plate_manager_wui import app as flask_app
from plate_manager_wui import set_car_park_system
from detector import LicensePlateDetector
from ocr_reader import OCRReader
import queue

# 日志配置
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"carpark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logger = logging.getLogger("CarParkSystem")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
console_handler.setFormatter(console_format)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

class CarParkSystem:
    def __init__(self):
        logger.debug("Initializing Car Park System")
        self.PORT = "/dev/ttyAMA0"
        self.BAUDRATE = 115200
        self.serial_conn = None
        logger.debug("Loading license plate detection model")
        self.detector = LicensePlateDetector(model_path="best.pt")
        logger.debug("Loading OCR model")
        self.ocr = OCRReader()
        self.db_conn = None
        self.camera_id = 0
        self.frame_width = 1280
        self.frame_height = 720
        logger.debug(f"Camera settings: ID={self.camera_id}, Resolution={self.frame_width}x{self.frame_height}")
        self.is_running = False
        self.current_frame = None
        self.camera_thread = None
        self.processed_plate = np.zeros((100, 300, 3), dtype=np.uint8)  # 初始化为黑色图像
        self.plate_text = "等待识别"
        self.last_process_time = 0  # 上次处理时间
        self.image_lock = threading.Lock()  # 图像访问锁
        self.db_lock = threading.Lock()  # 数据库访问锁
        self.recognition_stats = {"total": 0, "success": 0}  # 识别统计
        self.update_event = threading.Event()  # 用于通知前端更新的事件
        self.update_queue = queue.Queue(maxsize=1)  # 用于存储最新检测结果的队列

        logger.debug("Car Park System initialization complete")

    def connect_to_serial(self):
        logger.debug(f"Attempting to connect to STM32 on port {self.PORT} at {self.BAUDRATE} baud")
        try:
            self.serial_conn = serial.Serial(
                port=self.PORT,
                baudrate=self.BAUDRATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            logger.info(f"Connected to STM32 on {self.PORT}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to serial port: {e}")
            logger.debug(f"Serial connection error details: {str(e)}", exc_info=True)
            return False

    def get_processed_data(self):
        """获取处理后的车牌数据和文本"""
        # 尝试从队列获取最新结果
        try:
            plate_img, plate_text = self.update_queue.get_nowait()
            with self.image_lock:
                self.processed_plate = plate_img
                self.plate_text = plate_text
        except queue.Empty:
            pass
            
        with self.image_lock:
            if self.processed_plate is not None and self.plate_text is not None:
                ret, buffer = cv2.imencode('.jpg', self.processed_plate)
                if ret:
                    return buffer.tobytes(), self.plate_text
        # 返回默认值
        return cv2.imencode('.jpg', np.zeros((100, 300, 3), dtype=np.uint8))[1].tobytes(), "未检测到车牌"

    def get_recognition_accuracy(self):
        """获取识别准确率"""
        if self.recognition_stats["total"] == 0:
            return 0
        return round((self.recognition_stats["success"] / self.recognition_stats["total"]) * 100)

    def connect_to_database(self):
        db_path = 'car_park.db'
        logger.debug(f"Attempting to connect to database at {os.path.abspath(db_path)}")
        try:
            # 使用线程锁确保安全
            with self.db_lock:
                self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
                cursor = self.db_conn.cursor()

                # 检查表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plates'")
                if not cursor.fetchone():
                    logger.warning("Plates table not found in database. Creating it.")
                    cursor.execute(
                        "CREATE TABLE plates (id INTEGER PRIMARY KEY, plate_number TEXT, added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                    )
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS movement_log ("
                        "id INTEGER PRIMARY KEY, "
                        "plate_number TEXT, "
                        "action TEXT, "
                        "timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                    )
                    self.db_conn.commit()
                    logger.debug("Created database tables")

                logger.info("Connected to database successfully")
                return True
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return False

    def initialize_camera(self):
        logger.debug(f"Initializing camera (ID: {self.camera_id})")

        def camera_loop():
            logger.debug("Camera thread started")
            cap = cv2.VideoCapture(self.camera_id)
            if not cap.isOpened():
                logger.error(f"Failed to open camera with ID {self.camera_id}")
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            logger.debug(f"Camera parameters: {actual_width}x{actual_height} at {actual_fps} FPS")
            logger.info("Camera initialized successfully")
            frame_count = 0
            start_time = time.time()
            while self.is_running:
                ret, frame = cap.read()
                if ret:
                    self.current_frame = frame
                    frame_count += 1
                    if frame_count % 900 == 0:
                        elapsed = time.time() - start_time
                        fps = frame_count / elapsed if elapsed > 0 else 0
                        logger.debug(f"Camera capturing at {fps:.2f} FPS")
                        frame_count = 0
                        start_time = time.time()
                else:
                    logger.warning("Failed to capture frame from camera")
                time.sleep(0.03)
            logger.debug("Camera thread stopping")
            cap.release()
            logger.debug("Camera released")

        self.is_running = True
        self.camera_thread = threading.Thread(target=camera_loop, name="CameraThread")
        self.camera_thread.daemon = True
        self.camera_thread.start()
        logger.debug("Waiting for camera initialization")
        time.sleep(2)
        is_alive = self.camera_thread.is_alive()
        logger.debug(f"Camera thread status: {'Running' if is_alive else 'Failed'}")
        return is_alive

    def check_plate_in_database(self, plate_number):
        """检查车牌是否在数据库中（支持中英文混合比对）"""
        logger.debug(f"Checking plate '{plate_number}' in database")
        if not self.db_conn:
            logger.error("Database not connected")
            return False

        try:
            # 使用线程锁确保安全
            with self.db_lock:
                cursor = self.db_conn.cursor()

                # 首先尝试精确匹配
                cursor.execute("SELECT COUNT(*) FROM plates WHERE plate_number = ?", (plate_number,))
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.info(f"Plate {plate_number}: Exact match found")
                    return True

                # 如果没有精确匹配，尝试模糊匹配（移除特殊字符）
                clean_plate = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', plate_number)
                if clean_plate != plate_number:
                    cursor.execute("SELECT COUNT(*) FROM plates WHERE plate_number = ?", (clean_plate,))
                    count = cursor.fetchone()[0]
                    if count > 0:
                        logger.info(f"Plate {plate_number}: Cleaned match found ({clean_plate})")
                        return True

                logger.info(f"Plate {plate_number}: No match found")
                return False

        except Exception as e:
            logger.error(f"Database query error: {e}")
            return False

    def process_captured_image(self):
        logger.debug("Processing captured image for license plate detection")
        if self.current_frame is None:
            logger.error("No camera frame available")
            return None
        try:
            frame_shape = self.current_frame.shape
            logger.debug(f"Processing frame with shape: {frame_shape}")
            start_time = time.time()
            ret, buffer = cv2.imencode('.jpg', self.current_frame)
            if not ret:
                logger.error("Failed to encode image")
                return None
            jpg_bytes = BytesIO(buffer).getvalue()
            logger.debug(f"Image encoded to JPEG: {len(jpg_bytes)} bytes")
            detection_start = time.time()
            cropped_plate = self.detector.detect_and_crop(jpg_bytes)
            detection_time = time.time() - detection_start
            logger.debug(f"License plate detection took {detection_time:.3f} seconds")
            if cropped_plate is None:
                logger.warning("No license plate detected in the image")
                return None
            ocr_start = time.time()
            plate_text = self.ocr.read_text(cropped_plate)
            ocr_time = time.time() - ocr_start
            logger.debug(f"OCR processing took {ocr_time:.3f} seconds")
            if not plate_text:
                logger.warning("Could not read license plate text")
                return None

            # 更新识别统计
            self.recognition_stats["total"] += 1
            if plate_text and len(plate_text) > 3:  # 简单判断识别是否成功
                self.recognition_stats["success"] += 1

            # 存储处理结果并通知前端
            with self.image_lock:
                self.processed_plate = cropped_plate
                self.plate_text = plate_text
                self.last_process_time = time.time()
                
            # 将结果放入队列（用于立即更新前端）
            try:
                self.update_queue.put_nowait((cropped_plate, plate_text))
            except queue.Full:
                # 如果队列满，先清空再放入新结果
                try:
                    self.update_queue.get_nowait()
                except queue.Empty:
                    pass
                self.update_queue.put_nowait((cropped_plate, plate_text))
                
            # 通知前端有更新
            self.update_event.set()
            time.sleep(0.1)  # 确保事件被处理
            self.update_event.clear()

            return plate_text

        except Exception as e:
            logging.error(f"Error processing image: {e}")
            return None

    def get_current_frame(self):
        """获取当前摄像头帧的JPEG编码"""
        if self.current_frame is not None:
            ret, buffer = cv2.imencode('.jpg', self.current_frame)
            if ret:
                return buffer.tobytes()
        # 返回黑色图像作为占位符
        return cv2.imencode('.jpg', np.zeros((480, 640, 3), dtype=np.uint8))[1].tobytes()

    def log_movement(self, plate_number, action):
        if not self.db_conn:
            return
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "INSERT INTO movement_log (plate_number, action) VALUES (?, ?)",
                    (plate_number or "UNKNOWN", action)
                )
                self.db_conn.commit()
        except Exception as e:
            logger.error(f"记录日志错误: {e}")

    def _send_with_retry(self, message_bytes, max_retries=5):
        """带重试机制的串口发送（使用字节数据）"""
        if not self.serial_conn:
            logger.warning("串口连接不可用，无法发送消息")
            return False

        # 确保消息以换行符结尾
        if not message_bytes.endswith(b'\n'):
            message_bytes += b'\n'

        # 为了避免日志中的引号问题，我们提前解码并存储
        try:
            log_message = message_bytes.decode('utf-8').strip()
        except UnicodeDecodeError:
            log_message = repr(message_bytes)

        logger.debug(f"准备重试发送: {log_message}")

        for retry in range(max_retries):
            try:
                bytes_written = self.serial_conn.write(message_bytes)
                self.serial_conn.flush()  # 确保数据立即发送
                if bytes_written == len(message_bytes):
                    logger.info(f"已发送到STM32 (尝试 {retry + 1}/{max_retries}): {log_message}")
                    return True
                else:
                    logger.warning(
                        f"部分写入 (尝试 {retry + 1}/{max_retries}): {bytes_written}/{len(message_bytes)} 字节")
            except Exception as e:
                logger.warning(f"发送失败 (尝试 {retry + 1}/{max_retries}): {e}")
            time.sleep(0.02)  # 20ms 延迟

        logger.error(f"尝试 {max_retries} 次后发送失败: {log_message}")
        return False


    def force_plate_detection(self):
        """手动触发车牌检测"""
        logger.info("Manually triggering plate detection")
        plate_number = self.process_captured_image()

        if plate_number:
            is_authorized = self.check_plate_in_database(plate_number)
            if is_authorized:
                # 使用带重试的发送（字节格式）
                self._send_with_retry(b"OK")
                self.log_movement(plate_number, "ACCESS_GRANTED")
            else:
                self._send_with_retry(b"NO")
                self.log_movement(plate_number, "ACCESS_DENIED")
        else:
            self._send_with_retry(b"NO")
            self.log_movement(None, "未识别车牌")

        logger.info("Manual detection completed")

    def run_main_logic(self):
        """主系统运行逻辑"""
        logger.info("Starting main system logic")
        idle_count = 0
        while True:
            if self.serial_conn and self.serial_conn.in_waiting > 0:
                idle_count = 0
                serial_data = self.serial_conn.readline().decode('utf-8').strip()
                logger.info(f"Received from STM32: {serial_data}")
                if "CAR_DETECTED" in serial_data:
                    event_start = time.time()
                    time.sleep(0.1)  # 等待车辆稳定
                    plate_number = self.process_captured_image()

                    if plate_number:
                        is_authorized = self.check_plate_in_database(plate_number)
                        if is_authorized:
                            # 使用带重试的发送（字节格式）
                            self._send_with_retry(b"OK")
                            self.log_movement(plate_number, "ACCESS_GRANTED")
                        else:
                            self._send_with_retry(b"NO")
                            self.log_movement(plate_number, "ACCESS_DENIED")
                    else:
                        self._send_with_retry(b"NO")
                        self.log_movement(None, "未识别车牌")

                    event_time = time.time() - event_start
                    logger.debug(f"Event processing time: {event_time:.3f}s")
            else:
                idle_count += 1
                if idle_count >= 100:
                    idle_count = 0
            time.sleep(0.1)

    def run(self):
        logger.info("Starting Car Park System")
        if not self.connect_to_serial():
            logger.error("Failed to initialize serial connection")
            return

        if not self.connect_to_database():
            logger.error("Failed to initialize database")
            return

        if not self.initialize_camera():
            logger.error("Failed to initialize camera")
            return

        logger.info("System initialized and ready")

        try:
            # 设置全局变量
            set_car_park_system(self)
            logger.info("Car park system instance set in web interface")

            # 在后台线程中启动Web应用
            web_thread = threading.Thread(
                target=lambda: flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False),
                daemon=True
            )
            web_thread.start()
            logger.info(f"Web server started on http://0.0.0.0:5000")

            # 运行停车场主逻辑
            self.run_main_logic()

        except Exception as e:
            logger.critical(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    logger.debug("Script started")
    try:
        system = CarParkSystem()
        system.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)