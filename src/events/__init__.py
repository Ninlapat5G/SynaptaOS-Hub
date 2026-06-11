"""
events — ระบบ event-driven ของ Hub (ชั้น A: ระบบประสาท)

แหล่งเหตุการณ์ (sensor MQTT / telemetry มือถือ / เวลา) → bus → engine ประเมินกฎ
→ ทำเลยแบบ deterministic (สั่งอุปกรณ์/scene/เด้ง noti) หรือ escalate ขึ้นสมอง (pipeline)

ไฟล์: event(หน่วยเหตุการณ์) · bus(pub/sub) · values(ค่าปัจจุบันของเงื่อนไข)
      actions(ลงมือทำ) · engine(ประเมิน+ยิง) · rules(เก็บกฎ+MCP)
ดู docs/plan_events.md สำหรับภาพรวมสถาปัตยกรรม
"""
from .event import Event
from . import bus, engine, log, rules


def publish(event: Event) -> None:
    bus.publish(event)


def start() -> None:
    log.start()     # บันทึก feed เหตุการณ์ให้หน้า admin (เก็บในแรม)
    engine.start()


def stop() -> None:
    engine.stop()


def register(mcp) -> None:
    rules.register(mcp)
