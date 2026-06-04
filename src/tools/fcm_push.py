"""
fcm_push — ส่ง push ผ่าน Firebase Cloud Messaging

ใช้เป็น "ช่องสำรอง": เมื่อ Hub ส่งคำสั่งให้แอปผ่าน MQTT แล้วแอปไม่ตอบ (พับ/ถูกฆ่า/หลับ)
หรือ Hub อยากเด้งหาแอปตรง ๆ — FCM ปลุกเครื่องได้แม้แอปไม่ได้เปิดค้าง

ไม่ใช่ MCP tool (ไม่มี register) — เป็นฟังก์ชันภายในที่ account.py เรียกใช้
fcm_token ของแต่ละ user เก็บอยู่ใน profile.json (แอป sync ขึ้นมา)
"""

import config
import store

_app = None
_init_tried = False


def _ensure_app():
    """เปิด Firebase app ครั้งเดียว (lazy) — ไม่มี credential = คืน None (ปิด FCM)"""
    global _app, _init_tried
    if _app is not None:
        return _app
    if _init_tried:
        return None
    _init_tried = True
    if not config.FCM_CREDENTIALS:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        _app = firebase_admin.initialize_app(credentials.Certificate(config.FCM_CREDENTIALS))
    except Exception as e:
        print(f"[fcm] init failed: {e}")
        _app = None
    return _app


def send(user_id: str, title: str, body: str, data: dict | None = None) -> bool:
    """ส่ง FCM ไปเครื่องของ user (อ่าน fcmToken จาก profile). คืน True ถ้าส่งออกสำเร็จ

    ส่งแบบ **data-only** (ไม่มี notification block) ตั้งใจให้ระบบไม่โชว์ noti ดิบที่บริบทผิดเอง
    — ปล่อยให้ฝั่งแอป (ซิน) อ่าน data แล้วสร้าง noti ที่รู้ว่ามาจาก Hub ขึ้นมาเอง
    (title/body เก็บไว้เผื่อ debug แต่ไม่แนบไปกับ message)
    """
    if _ensure_app() is None:
        return False
    prof = store.load_part(user_id, "profile") or {}
    token = prof.get("fcmToken") or prof.get("fcm_token")
    if not token:
        return False
    from firebase_admin import messaging
    payload = {k: str(v) for k, v in (data or {}).items()}  # FCM data ต้องเป็น string ทั้งหมด
    # priority high + ไม่มี notification block → ปลุก onBackgroundMessage ฝั่งแอปแม้ตอนพับ/ถูกฆ่า
    msg = messaging.Message(
        token=token,
        data=payload,
        android=messaging.AndroidConfig(priority="high"),
    )
    try:
        messaging.send(msg)
        return True
    except Exception as e:
        print(f"[fcm] send failed: {e}")
        return False
