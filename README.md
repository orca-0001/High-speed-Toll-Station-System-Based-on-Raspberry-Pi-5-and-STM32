# 智行高速——基于树莓派5和STM32的高速路口智能收费站系统
作者：范财天

# 该项目是参考Lan Huong作者的开源项目制作的，链接如下
https://github.com/l4hu/Car-Park-License-Plate-Recognition-System

# 主要功能

1. 通过光敏传感器检测车辆；
2. 通过OLED显示信息（温湿度，二维码等）
3. 使用语音模块与蜂鸣器进行提示；
4. 通过摄像头实时监控并拍摄车牌图像；
5. 利用YOLO v8模型框选车牌区域并使用OCR技术识别车牌信息；
6. 根据数据库验证授权信息；
7. 通过Web界面实施查看路口画面与检测结果，并且有车辆的活动日志等等附加功能；
8. 根据检测结果控制道闸栏杆（舵机）；
9. 通过温湿度传感器控制风扇（电机）；
10. 最后道闸栏杆、风扇、车辆检测都附带了手动控制功能。

# 系统流程
系统由两部分组成：下位机（STM32），上位机（树莓派5），他们之间以三根线连接起来通过串口通信实现协同合作；

车辆接近时，光敏传感器接收信号，同时回传信号至STM32,STM32接收信号，触发语音提示，同时经串口通信启动树莓派车牌识别线程；该线程利用YOLO v8模型定位车牌，裁剪预处理后，结合OCR技术识别车牌文字；识别结果经授权判断模块与数据库比对，判定车辆通行权限。针对已授权车辆树莓派会回传通行指令，STM32控制舵机开启道闸；针对未授权车辆则回传拒绝指令，STM32保持道闸关闭并显示收费二维码，缴费完成后，系统控制道闸升起完成放行，在车辆离开后复位。



![image](https://github.com/user-attachments/assets/1c50a64c-d87b-4b9c-8810-c3d8237cec1d)

# 效果展示


登录页面

![image](https://github.com/user-attachments/assets/86aff8e6-3e2a-4b87-a54a-24c0bab7195c)

系统首页

![image](https://github.com/user-attachments/assets/ac550882-2b37-4e4e-b6bf-e7efc9bc345b)

监控页面

![image](https://github.com/user-attachments/assets/7df099e6-7fe0-43b3-9ed7-4a7d06b39a1a)

车牌数据库（已授权）

![image](https://github.com/user-attachments/assets/b0011523-32c4-4224-9e6b-b6a46a8d83a0)

活动日志

![783a11725d6d25d2fcf3b17ce03b12c](https://github.com/user-attachments/assets/0945b7d7-3abe-4851-8dc9-01a0d4164c2f)


下位机展示

![image](https://github.com/user-attachments/assets/9b49eabf-8166-4ef3-ad2a-d09a462973fa)


整体展示

![image](https://github.com/user-attachments/assets/b9991f16-bb38-47a3-a7ff-10bfa7a3f7e6)



# 已配置虚拟环境和配套代码的树莓派镜像系统的下载链接

https://pan.baidu.com/s/1P1Ga9XHYgDXEcnvbeHr1dA?pwd=fct7 
提取码：fct7


# 具体操作参考使用文档
使用文档总共有30页详细说明，全文六千多字，不怕你复现不出。



































