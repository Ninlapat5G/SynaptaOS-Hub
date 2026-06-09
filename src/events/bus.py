"""
bus — ป้ายกระจายเหตุการณ์ในเครื่อง (in-process pub/sub) เบา ๆ

ผู้ส่ง (source) เรียก publish(event) · ผู้รับ (rule engine) เรียก subscribe(fn)
handler รันใน thread ของผู้ส่ง (เช่น thread เครือข่ายของ MQTT) → ต้องเร็ว ห้ามบล็อก
งานหนัก/งานที่ต้องคิด ให้โยนเข้า pipeline pool เอา ไม่ทำใน handler
"""
import logging
import threading

_log = logging.getLogger("events.bus")
_subs = []
_lock = threading.Lock()


def subscribe(fn) -> None:
    with _lock:
        _subs.append(fn)


def publish(event) -> None:
    for fn in list(_subs):
        try:
            fn(event)
        except Exception as e:
            _log.error("event handler ล้มเหลว: %s", e)
