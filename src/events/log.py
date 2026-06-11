"""
log — สมุดบันทึกเหตุการณ์ล่าสุดของระบบ event-driven (เก็บในแรม ไม่เขียนดิสก์)

เก็บ 2 อย่าง: event ที่ไหลเข้า bus (device/node/phone) และการยิงกฎ (rule fire)
หน้า admin ใช้โชว์ feed ย้อนหลัง + broadcast สดผ่าน websocket เดิมของ webadmin
"""
import threading
import time
from collections import deque

_MAX = 300
_items: deque = deque(maxlen=_MAX)
_lock = threading.Lock()


def add(kind: str, text: str, detail: str = "") -> None:
    """kind: device | node | phone | rule | job — text สั้น ๆ อ่านรู้เรื่อง"""
    entry = {"ts": int(time.time()), "kind": kind, "text": text, "detail": detail}
    with _lock:
        _items.append(entry)
    # เด้งสดเข้าหน้า admin (best-effort — เว็บปิดอยู่ก็ไม่เป็นไร)
    try:
        import webadmin
        webadmin.broadcast_event(entry)
    except Exception:
        pass


def snapshot(limit: int = 200) -> list[dict]:
    with _lock:
        return list(_items)[-limit:]


def _on_event(ev) -> None:
    """ตัวฟัง bus — แปลง Event เป็นบรรทัดบันทึก"""
    try:
        add(ev.type, f"{ev.key} = {ev.value}")
    except Exception:
        pass


def start() -> None:
    from . import bus
    bus.subscribe(_on_event)
