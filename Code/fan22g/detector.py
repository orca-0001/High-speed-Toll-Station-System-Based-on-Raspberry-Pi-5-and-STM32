import cv2,torch,numpy as np
from ultralytics import YOLO
import logging,time,os
logger=logging.getLogger(__name__)
os.environ['CUDA_VISIBLE_DEVICES']='-1'

class LicensePlateDetector:
    def __init__(self,model_path="best.pt",conf_threshold=0.3):
        self.conf_threshold=conf_threshold
        try:
            self.device='cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"Initializing YOLOv8 detector with model: {model_path} on device: {self.device}")
            self.model=YOLO(model_path).to(self.device)
            self.model.fuse()
            logger.info(f"YOLOv8 model loaded and fused successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {str(e)}")
            raise
    
    def detect_and_crop(self,image_bytes):
        try:
            # Convert bytes to numpy array
            nparr=np.frombuffer(image_bytes,np.uint8)
            image=cv2.imdecode(nparr,cv2.IMREAD_COLOR)
            
            if image is None:
                logger.error("Failed to decode image")
                return None
            
            # Perform detection and return the cropped plate
            return self.detect_plate(image)
            
        except Exception as e:
            logger.error(f"Error in license plate detection: {str(e)}")
            return None
            
    def detect_plate(self,image):
        try:
            logger.info(f"Running license plate detection on image of shape: {image.shape}")
            results=self.model(image,conf=self.conf_threshold,iou=0.5,max_det=1,verbose=False)
            
            if not results or len(results[0].boxes) == 0:
                logger.warning("No license plates detected by YOLOv8")
                return None
                
            # Get the first (and assumed best) detection
            box = results[0].boxes[0]
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            
            logger.info(f"Detected license plate with confidence {conf:.2f} at coordinates: ({x1},{y1}) to ({x2},{y2})")
            
            # Add a small margin around the plate
            h, w = image.shape[:2]
            margin_y, margin_x = int((y2-y1)*0.05), int((x2-x1)*0.05)
            y1, y2 = max(0, y1-margin_y), min(h, y2+margin_y)
            x1, x2 = max(0, x1-margin_x), min(w, x2+margin_x)
            
            # Crop the license plate from the image
            plate_crop = image[y1:y2, x1:x2]
            
            if plate_crop.size == 0:
                logger.warning("Plate crop has zero size")
                return None
                
            # Save debug images if needed
            if os.environ.get('DEBUG_IMAGES', 'false').lower() == 'true':
                os.makedirs("debug_images", exist_ok=True)
                debug_image = image.copy()
                cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # cv2.imwrite(f"debug_images/plate_crop_{int(time.time()*1000)}.jpg", plate_crop)
            
            logger.info(f"Cropped plate image size: {plate_crop.shape}")
            return plate_crop
            
        except Exception as e:
            logging.error(f"Error in license plate detection: {str(e)}")
            # 返回一个黑色图像占位符
            return np.zeros((100, 300, 3), dtype=np.uint8)