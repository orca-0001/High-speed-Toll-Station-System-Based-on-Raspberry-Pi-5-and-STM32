
/* USER CODE BEGIN 0 */

//完美的一次！！！！！

#include "stm32f1xx_hal.h"
#include "main.h"
#include "i2c.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"
#include "ssd1306.h"
#include "ssd1306_fonts.h"
#include <string.h>
#include "ssd1306_tests.h"
#include "aht20.h"
#include "stdio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#define UART_RX_BUFFER_SIZE 64
#define UART_RX_CMD_SIZE 2

// 串口接收环形缓冲区结构
typedef struct {
    uint8_t buffer[UART_RX_BUFFER_SIZE];
    volatile uint16_t head;
    volatile uint16_t tail;
} UART_RxBuffer_t;

UART_RxBuffer_t uartRxBuffer = {0};
uint8_t uartCmd[UART_RX_CMD_SIZE];
uint8_t commandInProgress = 0; // 命令处理中标志

void ssd1306_NumInt(int number, uint8_t x, uint8_t y, SSD1306_Font_t Font, SSD1306_COLOR color)
{
    char buffer[16];
    sprintf(buffer, "%d", number);
    ssd1306_SetCursor(x, y);
    ssd1306_WriteString(buffer, Font, color);
}
/* USER CODE END Includes */

typedef enum
{
    NO_CAR,
    WAITING_RESPONSE,
} SystemState;

/* USER CODE BEGIN PD */
#define SERVO_OPEN 450
#define SERVO_CLOSED   1000
uint8_t servoState = 0;
int8_t Speed = 0;
uint8_t KeyNum0, KeyNum1, KeyNum2;

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
void UART_ProcessCommand(uint8_t *cmd);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/


// 从环形缓冲区读取一个字节
uint8_t UART_ReadByte(uint8_t *data)
{
    if(uartRxBuffer.head == uartRxBuffer.tail)
        return 0; // 缓冲区空

    *data = uartRxBuffer.buffer[uartRxBuffer.tail];
    uartRxBuffer.tail = (uartRxBuffer.tail + 1) % UART_RX_BUFFER_SIZE;
    return 1;
}



uint8_t Key_GetNum0(void)
{
    uint8_t KeyNum0 = 0;
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_12) == GPIO_PIN_RESET)
    {
        HAL_Delay(20);
        while (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_12) == GPIO_PIN_RESET);
        HAL_Delay(20);
        KeyNum0 = 1;
    }
    return KeyNum0;
}

uint8_t Key_GetNum1(void)
{
    uint8_t KeyNum1 = 0;
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_1) == GPIO_PIN_RESET)
    {
        HAL_Delay(20);
        while (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_1) == GPIO_PIN_RESET);
        HAL_Delay(20);
        KeyNum1 = 1;
    }
    return KeyNum1;
}

uint8_t Key_GetNum_2(void)
{
    uint8_t KeyNum2 = 0;
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_3) == GPIO_PIN_RESET)
    {
        HAL_Delay(20);
        while (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_3) == GPIO_PIN_RESET);
        HAL_Delay(20);
        KeyNum2 = 1;
    }
    return KeyNum2;
}

void Motor_SetSpeed(int8_t Speed)
{
    if (Speed >= 0)
    {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, Speed);
    }
}

void ManualControlServo(void)
{
    KeyNum2 = Key_GetNum_2();
    if (KeyNum2 == 1)
    {
        servoState = !servoState;
        if (servoState)
        {
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_OPEN);
        }
        else
        {
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_CLOSED);
        }
    }
}

// 处理接收到的命令
void UART_ProcessCommand(uint8_t *cmd)
{
    // 命令处理中标志，防止重入
    if(commandInProgress) return;
    commandInProgress = 1;

    if(cmd[0] == 'O' && cmd[1] == 'K')
    {
    	HAL_Delay(1700);  //等待上一句“车辆靠近”说完

    	//蜂鸣器提示一下
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_RESET);
        HAL_Delay(150);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_SET);

        HAL_Delay(200);  //稍等一下，提示完再说话

    	//请尽快通行的语音
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_RESET);
        HAL_Delay(100);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_14, GPIO_PIN_SET);

        HAL_Delay(500);   //稍等0.5秒然后升起栏杆

        __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_OPEN);

        // 新增逻辑：时刻检测光敏传感器的输出
        while (1)
        {
            GPIO_PinState carSensor = HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_1);
            uint8_t carDetected = (carSensor == GPIO_PIN_SET) ? 1 : 0; // 假设光敏传感器检测到物体时为高电平

            if (!carDetected) // 光敏传感器输出为低电平，执行落下操作
            {
                HAL_Delay(1500);
                __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_CLOSED);
                break; // 退出循环
            }
            else
            {
                // 光敏传感器输出为高电平，保持栏杆升起，继续检测
                HAL_Delay(100); // 避免过于频繁的检测
            }
        }

    }
    else if(cmd[0] == 'N' && cmd[1] == 'O')
    {
    	HAL_Delay(1700);  //等待上一句车辆靠近说完

    	//蜂鸣器提示一下
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_RESET);
        HAL_Delay(150);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_SET);

        HAL_Delay(200);  //稍等一下，提示完再说话

    	//请缴费的语音
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_RESET);
        HAL_Delay(100);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_13, GPIO_PIN_SET);

        ssd1306_TestDrawBitmap();
        HAL_Delay(4000);
    }

    commandInProgress = 0;
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_TIM2_Init();
    MX_I2C1_Init();
    MX_USART1_UART_Init();
    MX_TIM3_Init();

    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);

    // 重要：重新配置波特率后重新初始化
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK)
    {
        Error_Handler();
    }

    // 启用串口接收中断
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_RXNE);
    HAL_NVIC_SetPriority(USART1_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(USART1_IRQn);

    // 清空串口接收缓冲区
    uint8_t dummy;
    while(__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE)) {
        dummy = huart1.Instance->DR;
    }

    ssd1306_Init();
    AHT20_Init();
    float temperature, humidity;
    char message[50];
    int currentTemperature;
    int8_t Aut = 0, Flag = 0, Manual = 0;

    SystemState state = NO_CAR;
    uint8_t carDetectedPrevious = 0;
    uint32_t lastCarDetectionTime = 0;
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SERVO_CLOSED);

    // 初始化环形缓冲区
    uartRxBuffer.head = 0;
    uartRxBuffer.tail = 0;
    commandInProgress = 0;

    // 初始化完成后延时，确保系统稳定
    HAL_Delay(100);

    // 新增：车辆检测防抖变量
    uint32_t lastCarDetectTime = 0;
    uint8_t carDetectSent = 0;

    while (1)
    {
        GPIO_PinState carSensor = HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_1);
        uint8_t carDetected = (carSensor == GPIO_PIN_SET) ? 1 : 0;
        uint32_t currentTime = HAL_GetTick();

        ManualControlServo();

        // 新增：车辆检测防抖逻辑 - 修复多次发送问题
        if (carDetected && !carDetectedPrevious && (currentTime - lastCarDetectTime > 1000))
        {
            // 设置防抖时间，确保1秒内只检测一次
            lastCarDetectTime = currentTime;
            carDetectSent = 0; // 重置发送标志
        }

        switch (state)
        {
            case NO_CAR:
                // 新增：确保只发送一次车辆检测信号
                if (carDetected && !carDetectedPrevious && !carDetectSent && (currentTime - lastCarDetectTime < 100))
                {

                	//车辆靠近，等待检查的语音
                    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, GPIO_PIN_RESET);
                    HAL_Delay(100);
                    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, GPIO_PIN_SET);

                    char *carDetectMsg = "CAR_DETECTED\n";
                    // 只发送一次，不重试
                    HAL_UART_Transmit(&huart1, (uint8_t*)carDetectMsg, strlen(carDetectMsg), 100);

                    // 标记已发送
                    carDetectSent = 1;

                    state = WAITING_RESPONSE;
                    lastCarDetectionTime = currentTime;
                }
                break;

            case WAITING_RESPONSE:
                // 超时处理
                if (currentTime - lastCarDetectionTime > 3000)
                {
                    ssd1306_Fill(White);
                    ssd1306_SetCursor(0, 10);
                    ssd1306_WriteString("Timeout", Font_6x8, Black);
                    ssd1306_UpdateScreen();
                    state = NO_CAR;
                }
                break;
        }

        carDetectedPrevious = carDetected;
        HAL_Delay(10);

        // 处理接收到的UART数据
        static uint8_t cmdIndex = 0;
        static uint32_t lastByteTime = 0;
        uint8_t rxByte;
        uint32_t currentByteTime = HAL_GetTick();

        while(UART_ReadByte(&rxByte))
        {
            // 检查字节间隔时间，如果超过20ms则重置命令索引
            if(currentByteTime - lastByteTime > 20 && cmdIndex > 0) {
                cmdIndex = 0; // 超时重置
            }

            lastByteTime = currentByteTime;

            // 存储接收到的字节
            if(cmdIndex < UART_RX_CMD_SIZE) {
                uartCmd[cmdIndex++] = rxByte;
            }

            // 收到完整命令
            if(cmdIndex == UART_RX_CMD_SIZE) {
                UART_ProcessCommand(uartCmd);

                // 如果处于等待状态，切换到无车状态
                if(state == WAITING_RESPONSE) {
                    state = NO_CAR;
                }

                cmdIndex = 0; // 重置索引
            }
        }

        // 如果超过50ms没有收到新字节，重置命令索引
        if(cmdIndex > 0 && (HAL_GetTick() - lastByteTime > 50)) {
            cmdIndex = 0;
        }

        // 按键处理
        KeyNum0 = Key_GetNum0();
        if(KeyNum0 == 1)
        {
            Flag += 1;
            if(Flag == 2)
            {
                Flag = 0;
            }
        }

        // 温湿度处理
        AHT20_Measure();
        temperature = AHT20_Temperature();
        currentTemperature = (int)temperature;
        humidity = AHT20_Humidity();

        // OLED显示
        ssd1306_Fill(White);
        ssd1306_SetCursor(8, 0);
        ssd1306_WriteString("ETC System", Font_11x18, Black);
        sprintf(message, "Temperature: %.1f", temperature);
        ssd1306_SetCursor(0, 32);
        ssd1306_WriteString(message, Font_7x10, Black);
        sprintf(message, "Humidity: %.1f%%", humidity);
        ssd1306_SetCursor(0, 50);
        ssd1306_WriteString(message, Font_7x10, Black);
        ssd1306_UpdateScreen();

        // 风扇控制
        if(Flag == 1)
        {
            if (currentTemperature < 27)
            {
                Aut = 0;
            }
            else if (currentTemperature >= 27 && currentTemperature < 29)
            {
                Aut = 25;
            }
            else if (currentTemperature >= 29 && currentTemperature <= 100)
            {
                Aut = 49;
            }
        }

        if(Flag == 0)
        {
            KeyNum1 = Key_GetNum1();
            if (KeyNum1 == 1)
            {
                Manual += 25;
                if (Manual > 50)
                {
                    Manual = 0;
                }
                Aut = Manual;
            }
        }

        Motor_SetSpeed(Aut);
    }
}

void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                                |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
    {
        Error_Handler();
    }
}

/* USER CODE BEGIN 4 */
// USART1中断处理函数
// 串口接收到新数据时，触发中断并读取数据
void USART1_IRQHandler(void)
{
    // 只处理接收中断
    if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_RXNE) != RESET)  //检查接收数据标志（RXNE=1表示有数据）
    {
        // 读取数据寄存器（自动清除RXNE标志）
        uint8_t data = (uint8_t)(huart1.Instance->DR);  // 读取数据寄存器（DR），自动清除RXNE标志

        // 安全地将数据存入环形缓冲区
        uint16_t next_head = (uartRxBuffer.head + 1) % UART_RX_BUFFER_SIZE;

        // 检查缓冲区是否已满
        if (next_head != uartRxBuffer.tail)
        {
            uartRxBuffer.buffer[uartRxBuffer.head] = data;
            uartRxBuffer.head = next_head;
        }
        else
        {
            // 缓冲区满，丢弃最旧的数据
            uartRxBuffer.tail = (uartRxBuffer.tail + 1) % UART_RX_BUFFER_SIZE;
            uartRxBuffer.buffer[uartRxBuffer.head] = data;
            uartRxBuffer.head = next_head;
        }
    }

    // 清除可能的溢出错误
    if (__HAL_UART_GET_FLAG(&huart1, UART_FLAG_ORE))
    {
        __HAL_UART_CLEAR_OREFLAG(&huart1);
    }
}
/* USER CODE END 4 */

void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
}
#endif

/* USER CODE END 0 */

