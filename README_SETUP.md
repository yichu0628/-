# 流光 Glance - 配置指南

本文档说明如何配置 PC 端和 ESP32 硬件端，使项目能够正常运行。

---

## 目录

1. [PC 端配置](#pc-端配置)
2. [ESP32 硬件端配置](#esp32-硬件端配置)
3. [快速启动](#快速启动)
4. [常见问题](#常见问题)

---

## PC 端配置

### 1. 安装 Python 依赖

确保您已安装 Python 3.10 或更高版本，然后运行：

```bash
cd glance/pc
pip install -r requirements.txt
```

### 2. 配置 config.yaml

打开 `pc/config.yaml` 文件，填写以下必要信息：

#### 大模型 API 配置

```yaml
llm:
  base_url: "https://api.stepfun.com/v1"  # 阶跃星辰 API 地址
  api_key: "YOUR_API_KEY_HERE"             # 替换为您的 API 密钥
  model: "step-1v-8k"                      # 支持视觉的模型
```

**获取阶跃星辰 API 密钥：**
1. 访问 [阶跃星辰开放平台](https://platform.stepfun.com/)
2. 注册/登录账号
3. 在控制台创建 API Key

**使用其他大模型服务：**
- OpenAI: `base_url: "https://api.openai.com/v1"`, `model: "gpt-4-vision-preview"`
- 其他兼容服务：修改 `base_url` 和 `model` 即可

#### MQTT 配置

```yaml
mqtt:
  broker: "broker.emqx.io"     # 公共测试服务器
  port: 1883
  topic: "glance/tasks"
  client_id: "glance_pc_client"
```

**使用公共服务器（默认）：**
- 直接使用 `broker.emqx.io` 即可，无需修改

**使用私有 MQTT 服务器：**
```yaml
mqtt:
  broker: "your-mqtt-server.com"
  port: 1883
  username: "your_username"    # 如需认证
  password: "your_password"
```

#### TTS 配置（可选）

```yaml
tts:
  enabled: true                          # 启用语音播报
  api_key: "YOUR_TTS_API_KEY_HERE"       # 阶跃星辰 TTS API 密钥
```

### 3. 配置截图快捷键

```yaml
screenshot:
  hotkey: "ctrl+shift+s"     # 触发截图的快捷键
  watch_clipboard: true      # 是否监听剪贴板截图
```

---

## ESP32 硬件端配置

### 1. 硬件准备

| 组件 | 规格 | 数量 |
|------|------|------|
| 开发板 | ESP32-S3-DevKitC 或兼容板 | 1 |
| TFT 屏幕 | 240x240 ST7789 SPI 接口 | 1 |
| LED 灯带 | WS2812B (8 颗 LED) | 1 |
| 杜邦线 | 母对母 | 若干 |

### 2. 接线说明

#### TFT 屏幕 (ST7789) 接线

| TFT 引脚 | ESP32-S3 引脚 | 说明 |
|----------|---------------|------|
| VCC | 3.3V | 电源 |
| GND | GND | 地 |
| SCK | GPIO 12 | SPI 时钟 |
| SDA/MOSI | GPIO 11 | SPI 数据 |
| RES | GPIO 9 | 复位 |
| DC | GPIO 8 | 数据/命令选择 |
| CS | GPIO 10 | 片选 |
| BL | 3.3V | 背光（可选接 PWM 调光） |

#### LED 灯带接线

| LED 引脚 | ESP32-S3 引脚 |
|----------|---------------|
| VCC | 5V |
| GND | GND |
| DIN | GPIO 48 |

### 3. Arduino IDE 配置

#### 安装开发板支持

1. 打开 Arduino IDE
2. 进入 `文件` → `首选项`
3. 在"附加开发板管理器网址"中添加：
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
4. 进入 `工具` → `开发板` → `开发板管理器`
5. 搜索 "esp32" 并安装 "ESP32 by Espressif Systems"

#### 安装库依赖

在 Arduino IDE 中，进入 `工具` → `管理库`，搜索并安装：

- **TFT_eSPI** by Bodmer
- **PubSubClient** by Nick O'Leary
- **Adafruit NeoPixel** by Adafruit
- **ArduinoJson** by Benoit Blanchon

#### 配置 TFT_eSPI

1. 找到 TFT_eSPI 库的安装目录
2. 打开 `User_Setup.h` 文件
3. 注释掉默认配置，启用以下配置：

```cpp
// ST7789 240x240 显示屏
#define ST7789_DRIVER
#define TFT_WIDTH 240
#define TFT_HEIGHT 240

// SPI 引脚配置 (ESP32-S3)
#define TFT_MOSI 11
#define TFT_SCLK 12
#define TFT_CS   10
#define TFT_DC   8
#define TFT_RST  9

// 颜色顺序
#define TFT_RGB_ORDER TFT_RGB
```

### 4. 修改固件配置

打开 `esp32/glance_display/glance_display.ino`，修改以下配置：

```cpp
// Wi-Fi 配置
const char* WIFI_SSID = "YOUR_WIFI_SSID";        // 您的 Wi-Fi 名称
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"; // 您的 Wi-Fi 密码

// MQTT 配置（与 PC 端保持一致）
const char* MQTT_BROKER = "broker.emqx.io";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "glance/tasks";

// LED 引脚（根据实际接线修改）
#define LED_PIN 48
#define LED_COUNT 8
```

### 5. 上传固件

1. 用 USB 线连接 ESP32-S3 到电脑
2. 在 Arduino IDE 中选择：
   - 开发板：`ESP32S3 Dev Module`
   - USB CDC On Boot：`Enabled`
   - 端口：选择对应的 COM 端口
3. 点击上传按钮

---

## 快速启动

### PC 端启动

```bash
cd glance/pc
python main.py
```

启动后：
- 按 `Ctrl+Shift+S` 触发截图
- 截图会自动发送给大模型解析
- 解析出的任务会同步到 ESP32 硬件端

### 验证连接

1. **PC 端**：查看终端输出，确认 MQTT 连接成功
2. **ESP32 端**：查看串口监视器（波特率 115200），确认 Wi-Fi 和 MQTT 连接成功
3. **测试同步**：在 PC 端添加任务，观察 ESP32 屏幕是否更新

---

## 常见问题

### Q: PC 端截图无反应

**A:** 检查以下几点：
1. 确认快捷键格式正确（如 `ctrl+shift+s`）
2. 检查是否有其他软件占用了相同快捷键
3. 尝试使用剪贴板监听功能（复制截图）

### Q: MQTT 连接失败

**A:** 可能原因：
1. 网络问题：检查网络连接
2. 服务器问题：尝试使用其他公共 MQTT 服务器
3. 端口被封锁：尝试使用 WebSocket 端口（8083）

### Q: ESP32 屏幕不显示

**A:** 检查以下几点：
1. 确认 TFT_eSPI 的 `User_Setup.h` 配置正确
2. 检查屏幕接线是否正确
3. 确认屏幕背光已点亮

### Q: 大模型解析失败

**A:** 可能原因：
1. API Key 无效：检查 `config.yaml` 中的配置
2. 模型不支持视觉：确保使用支持视觉的模型（如 `step-1v-8k`）
3. 网络问题：检查网络连接

### Q: LED 不亮

**A:** 检查以下几点：
1. 确认 LED 引脚配置正确
2. 检查 LED 灯带供电是否正常
3. 确认 LED 数量配置正确

---

## 项目文件结构

```
glance/
├── pc/
│   ├── main.py                 # 主入口程序
│   ├── screenshot_listener.py  # 截图监听模块
│   ├── llm_parser.py           # 大模型解析模块
│   ├── task_manager.py         # 任务管理模块
│   ├── mqtt_client.py          # MQTT 通信模块
│   ├── tts_stepfun.py          # TTS 语音播报模块
│   ├── config.yaml             # 配置文件
│   └── requirements.txt        # Python 依赖
├── esp32/
│   └── glance_display/
│       └── glance_display.ino  # ESP32 固件
└── README_SETUP.md             # 本文档
```

---

## 技术支持

如有问题，请检查：
1. 各模块的日志输出
2. ESP32 串口监视器输出
3. 网络连接状态

祝您使用愉快！
