"""
telemetry — รับสถานะมือถือ (แบต/ตำแหน่ง) จากแอปผ่าน MQTT แล้วเก็บลง store

แทน heartbeat เดิมที่แอปดันขึ้นมาทุก 90 วิผ่าน MCP — ตอนนี้แอป publish เฉพาะตอนค่าเปลี่ยน
มาที่ topic users/<user_id>/telemetry (Hub แจก topic นี้ให้ตอน register)

แยกเป็น client ของตัวเอง (คนละตัวกับ discovery) — subscribe ค้างไว้ฟังของทุก user
"""

import json
import logging

import paho.mqtt.client as mqtt

import config
import store

_log = logging.getLogger("telemetry")
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
        _log.info("เชื่อม broker + subscribe %s", sub_topic)

    def on_disconnect(c, u, disconnect_flags, rc, props=None):
        _log.warning("หลุดจาก broker (rc=%s) — paho จะต่อใหม่ให้เอง", rc)

    def on_message(c, u, msg):
        uid = _uid_from_topic(msg.topic)
        if not uid or not store.is_registered(uid):
            return
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        store.save_part(uid, "phone", data)
        _log.info("รับ telemetry จาก %s: แบต %s%%%s",
                  uid, data.get("level", "?"),
                  " (กำลังเคลื่อนที่)" if data.get("moving") else "")
        # ป้อนเข้าระบบ event-driven → กฎที่อิงแบต/ชาร์จของคนนี้ถูกประเมินทันที (ไม่ต้องรอ tick)
        try:
            import events
            events.publish(events.Event(type="phone", key=uid, value=str(data.get("level", "")), user_id=uid))
        except Exception as e:
            _log.error("publish event ล้มเหลว: %s", e)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
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
