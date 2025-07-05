import logging, cv2, numpy as np, os, re
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'


class OCRReader:
    def __init__(self, lang='ch', use_angle_cls=True, det=True, rec=True):
        try:
            # 使用中文模型以支持中文车牌识别
            self.ocr = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)
            logger.info("PaddleOCR initialized successfully (CPU mode) with Chinese support")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            raise

    def preprocess_image(self, image):
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 自适应直方图均衡化，增强对比度
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # 使用高斯模糊减少噪声
            blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

            # 自适应阈值处理
            binary = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )

            # 形态学操作（开运算）去除小噪点
            kernel = np.ones((3, 3), np.uint8)
            processed = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

            return processed
        except Exception as e:
            logger.error(f"Error in preprocessing: {str(e)}")
            return image

    def read_text(self, image):
        try:
            # 使用原始图像和预处理后的图像进行双重识别
            results1 = self.ocr.ocr(image, cls=True)
            preprocessed = self.preprocess_image(image)
            results2 = self.ocr.ocr(preprocessed, cls=True)

            all_results = []

            # 处理第一次识别结果
            if results1 and results1[0]:
                for res in results1[0]:
                    text = res[1][0]
                    confidence = res[1][1]
                    # 只保留可能为车牌的文本（长度在5-10个字符之间）
                    if 5 <= len(text) <= 10:
                        all_results.append((text, confidence))

            # 处理第二次识别结果
            if results2 and results2[0]:
                for res in results2[0]:
                    text = res[1][0]
                    confidence = res[1][1]
                    if 5 <= len(text) <= 10:
                        all_results.append((text, confidence))

            # 如果没有结果，返回空
            if not all_results:
                logger.warning("No valid text detected in license plate")
                return None

            # 按置信度排序
            all_results.sort(key=lambda x: x[1], reverse=True)

            # 尝试匹配车牌模式
            plate_patterns = [
                r'^[\u4e00-\u9fff][A-Za-z][0-9A-Za-z]{5}$',  # 普通车牌：汉字+字母+5位数字字母
                r'^[\u4e00-\u9fff][A-Za-z][0-9A-Za-z]{4}$',  # 新能源车牌：汉字+字母+4位数字字母
                r'^[0-9A-Za-z]{6,7}$'  # 无汉字车牌
            ]

            # 优先选择匹配车牌模式的结果
            for text, confidence in all_results:
                for pattern in plate_patterns:
                    if re.match(pattern, text):
                        logger.info(f"Matched plate pattern: {text} (confidence: {confidence:.2f})")
                        return text

            # 如果没有匹配模式，返回置信度最高的结果
            best_text = all_results[0][0]
            logger.info(f"Using highest confidence result: {best_text}")
            return best_text

        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            return None
    def _similarity_score(self,str1,str2):
        if not str1 or not str2:
            return 0
        matches=sum(c1==c2 for c1,c2 in zip(str1,str2))
        return matches/max(len(str1),len(str2))
    def _is_valid_plate(self,text):
        patterns=[r'^\d{2}[A-Z][0-9]{4,5}$',r'^\d{2}[A-Z][0-9]{3}\.[0-9]{2}$']
        cleaned=''.join(ch for ch in text if ch.isalnum()).upper()
        for pattern in patterns:
            if re.match(pattern,cleaned):
                return True
        return False
    def _is_valid_motorcycle_plate(self,text):
        patterns=[r'^\d{2}[A-Z][0-9]{5,6}$',r'^\d{2}[A-Z][0-9]{2,3}\d{3}$']
        cleaned=''.join(ch for ch in text if ch.isalnum()).upper()
        for pattern in patterns:
            if re.match(pattern,cleaned):
                return True
        return False
