/**
 * 流光 Glance - ESP32-S3 硬件端固件
 * 
 * 功能：
 * - 连接 Wi-Fi 和 MQTT 服务器
 * - 接收并显示 PC 端推送的任务列表
 * - 通过 LED 灯带提供氛围反馈
 * 
 * 硬件要求：
 * - ESP32-S3 开发板
 * - 240x240 ST7789 TFT 屏幕（SPI 接口）
 * - WS2812B LED 灯带
 * 
 * 库依赖（通过 Arduino IDE 库管理器安装）：
 * - TFT_eSPI by Bodmer
 * - PubSubClient by Nick O'Leary
 * - Adafruit NeoPixel by Adafruit
 * - ArduinoJson by Benoit Blanchon
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <TFT_eSPI.h>
#include <SPI.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// ==================== 配置区域 ====================

// Wi-Fi 配置（请修改为您的网络信息）
const char* WIFI_SSID = "YOUR_WIFI_SSID";        // Wi-Fi 名称
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"; // Wi-Fi 密码

// MQTT 配置
const char* MQTT_BROKER = "broker.emqx.io";  // MQTT 服务器地址
const int MQTT_PORT = 1883;                   // MQTT 端口
const char* MQTT_TOPIC = "glance/tasks";      // 订阅主题
const char* MQTT_CLIENT_ID = "glance_esp32";  // 客户端 ID

// LED 配置
#define LED_PIN 48          // LED 数据引脚（根据您的接线修改）
#define LED_COUNT 8         // LED 数量
#define LED_BRIGHTNESS 50   // 亮度 (0-255)

// 屏幕配置（TFT_eSPI User_Setup.h 中配置引脚）
// 默认 SPI 引脚：
// MOSI: 11, MISO: 13, SCK: 12, CS: 10, DC: 8, RST: 9

// ==================== 全局对象 ====================

TFT_eSPI tft = TFT_eSPI();
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
Adafruit_NeoPixel ledStrip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// 任务数据结构
struct Task {
  String id;
  String task;
  String deadline;
  int priority;
  String status;
};

#define MAX_TASKS 10
Task tasks[MAX_TASKS];
int taskCount = 0;

// 状态变量
unsigned long lastUpdateTime = 0;
bool wifiConnected = false;
bool mqttConnected = false;
unsigned long lastMessageTime = 0;

// LED 动画状态
int ledAnimationState = 0;
unsigned long lastLedUpdate = 0;
int ledBrightness = 0;
int ledDirection = 1;

// ==================== 函数声明 ====================

void setupWiFi();
void setupMQTT();
void setupDisplay();
void setupLED();
void connectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void parseTasks(const char* jsonStr);
void displayTasks();
void displayStatus();
void updateLED();
void setLEDColor(uint8_t r, uint8_t g, uint8_t b);
void breathingLED(uint8_t r, uint8_t g, uint8_t b);
void blinkLED(uint8_t r, uint8_t g, uint8_t b);
void clearDisplay();
void drawCenteredText(const char* text, int y, uint16_t color);
String getTimeRemaining(const char* deadline);
void scrollText(int x, int y, int maxWidth, const char* text, uint16_t color);

// ==================== Setup ====================

void setup() {
  Serial.begin(115200);
  Serial.println("\n\n=== 流光 Glance ESP32-S3 ===");
  Serial.println("启动中...");

  // 初始化屏幕
  setupDisplay();
  
  // 初始化 LED
  setupLED();
  
  // 显示启动画面
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  drawCenteredText("Glance", 100, TFT_CYAN);
  tft.setTextSize(1);
  drawCenteredText("正在连接 Wi-Fi...", 130, TFT_WHITE);
  
  // 连接 Wi-Fi
  setupWiFi();
  
  // 设置 MQTT
  setupMQTT();
  
  Serial.println("初始化完成");
}

// ==================== Main Loop ====================

void loop() {
  // 维护 Wi-Fi 连接
  if (WiFi.status() != WL_CONNECTED) {
    wifiConnected = false;
    Serial.println("Wi-Fi 断开，尝试重连...");
    setupWiFi();
  } else {
    wifiConnected = true;
  }
  
  // 维护 MQTT 连接
  if (wifiConnected && !mqttClient.connected()) {
    mqttConnected = false;
    connectMQTT();
  }
  
  // MQTT 循环
  if (wifiConnected) {
    mqttClient.loop();
  }
  
  // 更新显示（每秒刷新一次倒计时）
  if (millis() - lastUpdateTime > 1000) {
    displayTasks();
    displayStatus();
    lastUpdateTime = millis();
  }
  
  // 更新 LED 动画
  updateLED();
  
  delay(10);
}

// ==================== Wi-Fi 设置 ====================

void setupWiFi() {
  Serial.print("连接 Wi-Fi: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\nWi-Fi 连接成功");
    Serial.print("IP 地址: ");
    Serial.println(WiFi.localIP());
    
    // 显示连接成功
    tft.fillRect(0, 120, 240, 20, TFT_BLACK);
    drawCenteredText("Wi-Fi 已连接", 130, TFT_GREEN);
  } else {
    wifiConnected = false;
    Serial.println("\nWi-Fi 连接失败");
    
    tft.fillRect(0, 120, 240, 20, TFT_BLACK);
    drawCenteredText("Wi-Fi 连接失败", 130, TFT_RED);
  }
}

// ==================== MQTT 设置 ====================

void setupMQTT() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setKeepAlive(60);
  mqttClient.setSocketTimeout(30);
}

void connectMQTT() {
  Serial.print("连接 MQTT: ");
  Serial.print(MQTT_BROKER);
  Serial.print(":");
  Serial.println(MQTT_PORT);
  
  tft.fillRect(0, 140, 240, 20, TFT_BLACK);
  drawCenteredText("连接 MQTT...", 150, TFT_YELLOW);
  
  if (mqttClient.connect(MQTT_CLIENT_ID)) {
    mqttConnected = true;
    Serial.println("MQTT 连接成功");
    
    // 订阅主题
    if (mqttClient.subscribe(MQTT_TOPIC)) {
      Serial.print("已订阅主题: ");
      Serial.println(MQTT_TOPIC);
    }
    
    tft.fillRect(0, 140, 240, 20, TFT_BLACK);
    drawCenteredText("MQTT 已连接", 150, TFT_GREEN);
  } else {
    mqttConnected = false;
    Serial.print("MQTT 连接失败，状态: ");
    Serial.println(mqttClient.state());
    
    tft.fillRect(0, 140, 240, 20, TFT_BLACK);
    drawCenteredText("MQTT 连接失败", 150, TFT_RED);
  }
}

// ==================== MQTT 回调 ====================

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("收到消息 [");
  Serial.print(topic);
  Serial.print("]: ");
  
  // 将 payload 转换为字符串
  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  Serial.println(message);
  
  // 解析任务
  parseTasks(message);
  
  // 更新最后消息时间
  lastMessageTime = millis();
  
  // 新任务 LED 效果（绿色闪烁）
  ledAnimationState = 1;  // 闪烁模式
  lastLedUpdate = millis();
}

// ==================== 任务解析 ====================

void parseTasks(const char* jsonStr) {
  // 使用 ArduinoJson 解析
  StaticJsonDocument<2048> doc;
  DeserializationError error = deserializeJson(doc, jsonStr);
  
  if (error) {
    Serial.print("JSON 解析失败: ");
    Serial.println(error.c_str());
    return;
  }
  
  // 清空现有任务
  taskCount = 0;
  
  // 解析任务数组
  JsonArray taskArray = doc.as<JsonArray>();
  int index = 0;
  
  for (JsonObject taskObj : taskArray) {
    if (index >= MAX_TASKS) break;
    
    tasks[index].id = taskObj["id"].as<String>();
    tasks[index].task = taskObj["task"].as<String>();
    tasks[index].deadline = taskObj["deadline"].as<String>();
    tasks[index].priority = taskObj["priority"].as<int>();
    tasks[index].status = taskObj["status"].as<String>();
    
    index++;
    taskCount++;
  }
  
  Serial.print("解析到 ");
  Serial.print(taskCount);
  Serial.println(" 个任务");
  
  // 更新显示
  displayTasks();
  
  // 检查是否有今日截止的任务
  bool hasTodayTask = false;
  for (int i = 0; i < taskCount; i++) {
    if (tasks[i].deadline.length() > 0) {
      String remaining = getTimeRemaining(tasks[i].deadline.c_str());
      if (remaining.indexOf("小时") >= 0 || remaining.indexOf("分钟") >= 0) {
        hasTodayTask = true;
        break;
      }
    }
  }
  
  // 设置 LED 模式
  if (hasTodayTask) {
    ledAnimationState = 2;  // 红色呼吸（紧急任务）
  } else if (taskCount > 0) {
    ledAnimationState = 0;  // 蓝色常亮（有任务）
  } else {
    ledAnimationState = 0;  // 蓝色常亮（空闲）
  }
}

// ==================== 显示函数 ====================

void setupDisplay() {
  tft.init();
  tft.setRotation(0);  // 竖屏模式
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  
  Serial.println("屏幕初始化完成");
}

void displayTasks() {
  // 清屏
  tft.fillScreen(TFT_BLACK);
  
  // 绘制标题栏
  tft.fillRect(0, 0, 240, 30, TFT_NAVY);
  tft.setTextColor(TFT_WHITE, TFT_NAVY);
  tft.setTextSize(2);
  drawCenteredText("Glance 待办", 8, TFT_WHITE);
  
  // 绘制分隔线
  tft.drawFastHLine(0, 30, 240, TFT_CYAN);
  
  // 显示任务列表
  if (taskCount == 0) {
    tft.setTextColor(TFT_GRAY, TFT_BLACK);
    tft.setTextSize(1);
    drawCenteredText("暂无任务", 100, TFT_GRAY);
    drawCenteredText("按 Ctrl+Shift+S 截图添加", 120, TFT_DARKGREY);
  } else {
    int yPos = 40;
    int displayCount = min(taskCount, 3);  // 最多显示3条
    
    for (int i = 0; i < displayCount; i++) {
      // 优先级颜色
      uint16_t priorityColor;
      switch (tasks[i].priority) {
        case 1: priorityColor = TFT_RED; break;
        case 2: priorityColor = TFT_YELLOW; break;
        default: priorityColor = TFT_GREEN; break;
      }
      
      // 绘制优先级指示条
      tft.fillRect(0, yPos, 4, 50, priorityColor);
      
      // 任务名称
      tft.setTextColor(TFT_WHITE, TFT_BLACK);
      tft.setTextSize(1);
      tft.setCursor(10, yPos + 5);
      
      // 截断过长的任务名
      String taskName = tasks[i].task;
      if (taskName.length() > 20) {
        taskName = taskName.substring(0, 17) + "...";
      }
      tft.print(taskName);
      
      // 截止时间倒计时
      if (tasks[i].deadline.length() > 0) {
        String remaining = getTimeRemaining(tasks[i].deadline.c_str());
        
        // 根据剩余时间设置颜色
        uint16_t timeColor;
        if (remaining.indexOf("逾期") >= 0) {
          timeColor = TFT_RED;
        } else if (remaining.indexOf("小时") >= 0 || remaining.indexOf("分钟") >= 0) {
          timeColor = TFT_ORANGE;
        } else {
          timeColor = TFT_CYAN;
        }
        
        tft.setTextColor(timeColor, TFT_BLACK);
        tft.setCursor(10, yPos + 25);
        tft.print(remaining);
      }
      
      // 优先级标签
      tft.setTextColor(priorityColor, TFT_BLACK);
      tft.setCursor(200, yPos + 5);
      tft.print("P");
      tft.print(tasks[i].priority);
      
      yPos += 55;
    }
    
    // 显示更多任务提示
    if (taskCount > 3) {
      tft.setTextColor(TFT_GRAY, TFT_BLACK);
      tft.setTextSize(1);
      drawCenteredText(String("还有 ") + (taskCount - 3) + " 个任务", 205, TFT_GRAY);
    }
  }
}

void displayStatus() {
  // 状态栏背景
  tft.fillRect(0, 210, 240, 30, TFT_DARKGREY);
  
  // Wi-Fi 状态
  tft.setTextSize(1);
  if (wifiConnected) {
    tft.setTextColor(TFT_GREEN, TFT_DARKGREY);
    tft.setCursor(5, 218);
    tft.print("WiFi OK");
  } else {
    tft.setTextColor(TFT_RED, TFT_DARKGREY);
    tft.setCursor(5, 218);
    tft.print("WiFi X");
  }
  
  // MQTT 状态
  if (mqttConnected) {
    tft.setTextColor(TFT_GREEN, TFT_DARKGREY);
    tft.setCursor(70, 218);
    tft.print("MQTT OK");
  } else {
    tft.setTextColor(TFT_RED, TFT_DARKGREY);
    tft.setCursor(70, 218);
    tft.print("MQTT X");
  }
  
  // 任务数量
  tft.setTextColor(TFT_WHITE, TFT_DARKGREY);
  tft.setCursor(145, 218);
  tft.print("任务: ");
  tft.print(taskCount);
}

void clearDisplay() {
  tft.fillScreen(TFT_BLACK);
}

void drawCenteredText(const char* text, int y, uint16_t color) {
  int16_t x1, y1;
  uint16_t w, h;
  tft.getTextBounds(text, 0, y, &x1, &y1, &w, &h);
  tft.setCursor((240 - w) / 2, y);
  tft.setTextColor(color, TFT_BLACK);
  tft.print(text);
}

String getTimeRemaining(const char* deadline) {
  // 解析截止时间 (格式: YYYY-MM-DD HH:MM)
  int year, month, day, hour, minute;
  if (sscanf(deadline, "%d-%d-%d %d:%d", &year, &month, &day, &hour, &minute) != 5) {
    return "时间格式错误";
  }
  
  // 转换为时间戳（简化计算，假设当前年份）
  struct tm deadlineTm = {0};
  deadlineTm.tm_year = year - 1900;
  deadlineTm.tm_mon = month - 1;
  deadlineTm.tm_mday = day;
  deadlineTm.tm_hour = hour;
  deadlineTm.tm_min = minute;
  
  time_t deadlineTime = mktime(&deadlineTm);
  time_t now;
  time(&now);
  
  double diff = difftime(deadlineTime, now);
  
  if (diff < 0) {
    return "已逾期";
  }
  
  int days = (int)(diff / 86400);
  int hours = (int)((diff - days * 86400) / 3600);
  int minutes = (int)((diff - days * 86400 - hours * 3600) / 60);
  
  if (days > 0) {
    return String("还剩 ") + days + " 天 " + hours + " 小时";
  } else if (hours > 0) {
    return String("还剩 ") + hours + " 小时 " + minutes + " 分钟";
  } else {
    return String("还剩 ") + minutes + " 分钟";
  }
}

// ==================== LED 函数 ====================

void setupLED() {
  ledStrip.begin();
  ledStrip.setBrightness(LED_BRIGHTNESS);
  ledStrip.show();  // 初始化为关闭状态
  
  Serial.println("LED 初始化完成");
}

void updateLED() {
  unsigned long currentTime = millis();
  
  switch (ledAnimationState) {
    case 0:  // 蓝色常亮（空闲/有任务）
      setLEDColor(0, 0, 50);  // 深蓝色
      break;
      
    case 1:  // 绿色闪烁（收到新任务）
      if (currentTime - lastLedUpdate < 300) {
        setLEDColor(0, 100, 0);  // 绿色
      } else if (currentTime - lastLedUpdate < 600) {
        setLEDColor(0, 0, 0);  // 关闭
      } else {
        lastLedUpdate = currentTime;
        // 闪烁5次后回到正常状态
        static int blinkCount = 0;
        blinkCount++;
        if (blinkCount >= 10) {
          blinkCount = 0;
          ledAnimationState = 0;
        }
      }
      break;
      
    case 2:  // 红色呼吸（紧急任务）
      breathingLED(100, 0, 0);  // 红色呼吸
      break;
  }
}

void setLEDColor(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < LED_COUNT; i++) {
    ledStrip.setPixelColor(i, ledStrip.Color(r, g, b));
  }
  ledStrip.show();
}

void breathingLED(uint8_t r, uint8_t g, uint8_t b) {
  unsigned long currentTime = millis();
  
  if (currentTime - lastLedUpdate > 20) {
    ledBrightness += ledDirection * 2;
    
    if (ledBrightness >= 100) {
      ledBrightness = 100;
      ledDirection = -1;
    } else if (ledBrightness <= 0) {
      ledBrightness = 0;
      ledDirection = 1;
    }
    
    uint8_t actualR = (r * ledBrightness) / 100;
    uint8_t actualG = (g * ledBrightness) / 100;
    uint8_t actualB = (b * ledBrightness) / 100;
    
    setLEDColor(actualR, actualG, actualB);
    lastLedUpdate = currentTime;
  }
}

void blinkLED(uint8_t r, uint8_t g, uint8_t b) {
  static bool ledOn = false;
  unsigned long currentTime = millis();
  
  if (currentTime - lastLedUpdate > 500) {
    if (ledOn) {
      setLEDColor(0, 0, 0);
      ledOn = false;
    } else {
      setLEDColor(r, g, b);
      ledOn = true;
    }
    lastLedUpdate = currentTime;
  }
}
