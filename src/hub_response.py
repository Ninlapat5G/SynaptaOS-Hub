"""
hub_response — รับ "ผลลัพธ์" ที่ App ส่งกลับมาหลังทำคำสั่งจาก Hub (ปิดวงจร agent-to-agent)

เดิม send_command_to_user_app เป็น fire-and-forget (ส่ง FCM แล้วจบ ไม่รู้ผล).
ตอนนี้: App (เฉพาะตอนแอปเปิด/foreground process) ทำงานเสร็จ → publish ผลกลับมาที่
  {base}/users/<uid>/hub_response   (MQTT5)
พร้อมแนบ "ตัวตนเครื่องที่ตอบ" ใน MQTT5 user properties (device_id/user_id) ให้ Hub มั่นใจว่ามาจากใครจริง ๆ
และสะท้อน user_id ที่ Hub แนบไปกับ FCM ตอนแรกกลับมาในตัว payload ด้วย (echo) — ปิดวงจรได้ก็ต่อเมื่อ
corr_id + user_id ตรงกันทั้งคู่ เท่านั้น (กันกรณี token เพี้ยน/ตอบมั่ว/ผิดเครื่อง)

Hub subscribe ค้างไว้ แล้วจับคู่ด้วย corr_id → ปลุก thread ที่กำลังรอผลอยู่ (account.send_app_command)
ถ้า App พับ/ถูกฆ่า = ไม่มีใครตอบ → ฝั่งที่รอจะ timeout เองแล้วบอกว่า "ส่งแล้ว เดี๋ยวทำตอนเปิดแอป"
"""

import json
import logging
import threading

import paho.mqtt.client as mqtt

import config

_log = logging.getLogger("hub_response")
_client: mqtt.Client | None = None
_connected = False   # สถานะการต่อ broker (ใช้เป็นสัญญาณ "ระบบพร้อม" ตอนบูต)


def is_connected() -> bool:
    return _connected

_lock = threading.Lock()
_waiters: dict[str, dict] = {}   # corr_id -> {"event": Event, "result": dict|None, "uid": expected_uid}


def _uid_from_topic(topic: str) -> str | None:
    parts = topic.split("/")
    if "users" in parts:
        i = parts.index("users")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def arm(corr_id: str, expected_uid: str) -> None:
    """ลงทะเบียนรอผลก่อนส่งคำสั่งออกไป — กันผลกลับมาเร็วกว่าจะได้ลงทะเบียน (race)"""
    with _lock:
        _waiters[corr_id] = {"event": threading.Event(), "result": None, "uid": expected_uid}


def disarm(corr_id: str) -> None:
    """ยกเลิกการรอ (เช่น arm ไปแล้วแต่ส่ง FCM ไม่สำเร็จ) — ไม่ลบจะค้างใน dict ตลอด (รั่ว)"""
    with _lock:
        _waiters.pop(corr_id, None)


def collect(corr_id: str, timeout: float) -> dict | None:
    """รอผลของ corr_id ที่ arm ไว้ จนได้ผล หรือครบ timeout (วินาที)
    คืน dict {ok, detail, device_id} ถ้าได้ทัน · None ถ้า timeout"""
    with _lock:
        w = _waiters.get(corr_id)
    if not w:
        return None
    w["event"].wait(timeout)
    with _lock:
        w = _waiters.pop(corr_id, None)
    # อ่าน result ตรง ๆ ไม่อิงว่า wait ทันไหม — ผลที่มาเฉียดเส้น timeout จะได้ไม่ถูกทิ้ง
    return w["result"] if w else None


def start() -> None:
    global _client
    sub_topic = config.topic("users/+/hub_response")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)

    def on_connect(c, u, flags, rc, props=None):
        global _connected
        _connected = True
        c.subscribe(sub_topic, qos=1)
        _log.info("เชื่อม broker + subscribe %s", sub_topic)

    def on_disconnect(c, u, disconnect_flags, rc, props=None):
        global _connected
        _connected = False
        _log.warning("หลุดจาก broker (rc=%s) — paho จะต่อใหม่ให้เอง", rc)

    def on_message(c, u, msg):
        topic_uid = _uid_from_topic(msg.topic)
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        corr_id = data.get("corr_id", "")
        if not corr_id:
            return
        echoed_uid = str(data.get("user_id", ""))

        # ตัวตนเครื่องที่ตอบ — อ่านจาก MQTT5 user properties (เชื่อถือได้กว่ายัดใน payload)
        device_id, claimed_uid = "", ""
        props = getattr(msg, "properties", None)
        for k, v in (getattr(props, "UserProperty", None) or []):
            if k == "device_id":
                device_id = v
            elif k == "user_id":
                claimed_uid = v

        with _lock:
            w = _waiters.get(corr_id)
            if not w:
                return
            # ปิดวงจรได้ก็ต่อเมื่อ corr_id (จับคู่จาก dict key) และ user_id ที่ App แนบกลับมาตรงกับที่ Hub ส่งไปจริง
            # (echoed_uid = ค่าที่ส่งไปใน FCM payload ตอนแรก ต้องสะท้อนกลับมาเหมือนเดิม — กันตอบมั่ว/ผิดเครื่อง/token เพี้ยน)
            if topic_uid != w["uid"] or echoed_uid != w["uid"] or (claimed_uid and claimed_uid != w["uid"]):
                _log.warning("ทิ้งผลที่ไม่ตรงเจ้าของ: corr=%s topic_uid=%s echoed=%s claimed=%s รอ=%s",
                             corr_id, topic_uid, echoed_uid, claimed_uid, w["uid"])
                return
            w["result"] = {
                "ok": bool(data.get("ok")),
                "detail": str(data.get("detail", "")),
                "device_id": device_id,
            }
            w["event"].set()
        _log.info("รับผลจาก %s (device=%s): %s", topic_uid, device_id or "?", str(data.get("detail", ""))[:80])

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
