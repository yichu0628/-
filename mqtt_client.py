"""
MQTT 通信模块
负责将任务同步到硬件端。
"""

import json
from typing import Any, Dict, List, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


class MQTTManager:
    """MQTT 管理器，负责建立连接和发布任务消息。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 MQTT 管理器。

        Args:
            config: Optional[Dict[str, Any]] - MQTT 配置字典。

        Returns:
            None - 无返回值。
        """
        config = config or {}
        self.broker = config.get("broker", "broker.emqx.io")
        self.port = int(config.get("port", 1883))
        self.topic = config.get("topic", "glance/tasks")
        self.client_id = config.get("client_id", "glance_desktop_client")
        self.username = config.get("username", "")
        self.password = config.get("password", "")

        self._connected = False
        self._client = None

    def _create_client(self):
        """
        创建 MQTT 客户端实例。

        Args:
            无。

        Returns:
            object - MQTT 客户端对象。
        """
        if mqtt is None:
            raise RuntimeError("未安装 paho-mqtt，无法使用 MQTT 功能")

        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        except Exception:
            client = mqtt.Client(client_id=self.client_id)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect

        if self.username:
            client.username_pw_set(self.username, self.password)

        return client

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """
        处理 MQTT 连接成功事件。

        Args:
            client: object - MQTT 客户端。
            userdata: object - 用户数据。
            flags: object - 连接标记。
            reason_code: object - 返回码。
            properties: object - 连接属性。

        Returns:
            None - 无返回值。
        """
        code = getattr(reason_code, "value", reason_code)
        self._connected = code == 0
        print(f"[MQTT] 连接结果: {code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """
        处理 MQTT 断开事件。

        Args:
            client: object - MQTT 客户端。
            userdata: object - 用户数据。
            disconnect_flags: object - 断开标记。
            reason_code: object - 返回码。
            properties: object - 连接属性。

        Returns:
            None - 无返回值。
        """
        self._connected = False
        print(f"[MQTT] 已断开: {reason_code}")

    def start(self) -> bool:
        """
        启动 MQTT 连接。

        Args:
            无。

        Returns:
            bool - 是否连接成功。
        """
        try:
            self._client = self._create_client()
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception as exc:
            print(f"[MQTT] 启动失败: {exc}")
            self._connected = False
            return False

    def stop(self):
        """
        停止 MQTT 连接。

        Args:
            无。

        Returns:
            None - 无返回值。
        """
        if self._client is None:
            return

        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception as exc:
            print(f"[MQTT] 停止时出错: {exc}")
        finally:
            self._connected = False

    def is_connected(self) -> bool:
        """
        获取当前连接状态。

        Args:
            无。

        Returns:
            bool - 是否已连接。
        """
        return self._connected

    def sync_tasks(self, tasks: List[Dict[str, Any]]) -> bool:
        """
        同步任务列表到硬件端。

        Args:
            tasks: List[Dict[str, Any]] - 要同步的任务列表。

        Returns:
            bool - 是否发送成功。
        """
        if self._client is None:
            print("[MQTT] 客户端未初始化，跳过同步")
            return False

        payload = json.dumps(tasks, ensure_ascii=False)

        try:
            result = self._client.publish(self.topic, payload)
            status = getattr(result, "rc", 1)
            print(f"[MQTT] 已发布 {len(tasks)} 条任务到主题 {self.topic}")
            return status == 0
        except Exception as exc:
            print(f"[MQTT] 发布失败: {exc}")
            return False
