
如果是直接装的我给的系统（第一种方式），树莓派端的文件、配置都不用管，自带了，直接输入命令运行代码即可。
（具体参考使用文档）

语音模块文件是给语音模块内置的配置和音频：
只需要将里面的所有文件复制到JQ8900中即可（替换已有文件）它自带了一个内存卡，通过数据线与电脑相连即可传输数据。


ETC文件是32端的项目代码：
只需要将”ETC“文件导入到CubeIDE软件，然后在软件里打开main.c文件点击编译下载即可；
main代码文件在ETC\Core\Src里面。


fan22g文件是树莓派端的项目代码：
只需要将"fan22g"文件复制到树莓派系统的主文件里面即可，比如我复制到 home/pi 这个路径下；
那么启动该代码就只需要打开终端，输入命令。

conda activate yolo     (回车)        //这一行就是在conda里面启动虚拟环境"yolo" 
cd /home/pi/fan22g   (回车)        //这一行就是进入到项目代码文件里面
python main.py           (回车)        //这一行就是使用python运行 main.py 代码

注意正确顺序应该是：
语音模块文件替换-32端的代码下载-树莓派端的文件复制-连接树莓派-树莓派插上摄像头-树莓派上电启动-运行main.py代码
其中连接树莓派就是使用三根线将树莓派与STM32端连接起来，具体就是GND-GND,RX-TX,TX-RX这样相连；
（上电前一定要先插上摄像头，不然检测不到）


至此整个系统的代码就完整的运行了


查看Web页面：
确保查看网页端的设备（电脑，手机）与树莓派连接在同一个局域网，然后在设备的浏览器里面输入网址，也就是
树莓派的ip地址:5000  即可访问，比如：  192.168.36.51:5000     （具体需要自行查看你的树莓派ip地址是多少）
切记是http://192.168.36.51:5000  而不是https://192.168.36.51:5000  
保险起见直接从192开始输入，不要从http开始输入


注意以上只是关于代码文件的使用，而运行代码前需要做相应的环境配置，具体参考使用文档




