"""
telemetry — รับสถานะมือถือ (แบต/ตำแหน่ง) จากแอปผ่าน MQTT แล้วเก็บลง store

แทน heartbeat เดิมที่แอปดันขึ้นมาทุก 90 วิผ่าน MCP — ตอนนี้แอป publish เฉพาะตอนค่าเปลี่ยน
มาที่ topic users/<user_id>/telemetry (Hub แจก topic นี้ให้ตอน register)

แยกเป็น client ของตัวเอง (คนละตัวกับ discovery) — subscribe ค้างไว้ฟังของทุก user
"""

import json

import paho.mqtt.client as mqtt

import config
import store

_client: mqtt.Client | None = None


def _uid_from_topic(topic: str) -> str | None:
    """ดึง user_id จาก .../users/<uid>/telemetry"""
    parts = topic.split("/")
    if "users" in parts:
        i = parts.index("users")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def start() -> None:
    global _client
    sub_topic = config.topic("users/+/telemetry")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(c, u, flags, rc, props=None):
        c.subscribe(sub_topic, qos=1)
        print(f"[telemetry] subscribe {sub_topic}")

    def on_message(c, u, msg):
        uid = _uid_from_topic(msg.topic)
        if not uid or not store.is_registered(uid):
            return
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        store.save_part(uid, "phone", data)

    client.on_connect = on_connect
    client.on_message = on_message
    if config.MQTT_USE_TLS:
        import ssl
        client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=30)
    client.loop_start()
    _client = client


def stop() -> None:
    if _client:
        _client.loop_stop()
        _client.disconnect()
