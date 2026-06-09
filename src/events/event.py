"""
Event — หน่วย "เหตุการณ์" 1 ชิ้นที่ไหลในระบบ event-driven ของ Hub

ทุกแหล่ง (sensor MQTT, ตั้งเวลา, อุปกรณ์ออฟไลน์, มือถือ) แปลงสิ่งที่เกิดขึ้นเป็น Event
รูปเดียวกัน → ยิงเข้า bus → rule engine จับคู่กฎ → ทำ action
"""
import time
from dataclasses import dataclass, field


@dataclass
class Event:
    type: str                       # "device" | "schedule" | "device_offline" | "phone" | "geofence"
    key: str                        # ตัวระบุภายในชนิดนั้น (เช่น topic อุปกรณ์)
    value: str | None = None        # ค่าใหม่ (ถ้ามี)
    user_id: str | None = None      # เจ้าของ (ถ้าผูกกับคน)
    ts: float = field(default_factory=time.time)
    meta: dict = field(default_factory=dict)
