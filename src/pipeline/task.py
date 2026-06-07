"""
AgentTask — หน่วยงาน 1 ชิ้นที่ไหลผ่าน pipeline:
    source → queue → worker (agent.run) → output

output มีได้ 2 ทาง พร้อมกันก็ได้ (เลือกต่อ task):
    - reply : callback ตอบกลับ "แหล่งที่ส่งงานมา" (เช่น HTTP response, publish MQTT reply topic)
    - sinks : รายชื่อ sink เสริมที่จะส่งผลไปด้วย (เช่น ['fcm', 'log']) — ดู pipeline/sinks.py
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class AgentTask:
    task: str                                       # คำสั่งภาษาคนที่จะให้ agent ทำ
    user_id: Optional[str] = None                   # บริบทผู้ใช้ (ให้ agent ดึงข้อมูล/ส่งกลับถูกคน)
    source: str = "unknown"                         # ชื่อแหล่งที่ส่งงานเข้ามา (ไว้ log/debug/route)
    allow_power: bool = False                       # อนุญาตคำสั่งปิด/รีสตาร์ทเครื่องไหม (เฉพาะที่มาจากผู้ใช้จริง)

    # None = ให้ agent ใช้ "ความจำ session" ของ user (บทสนทนาต่อเนื่อง) · [] = ไม่ยุ่ง session (งานเดี่ยว)
    history: Optional[list] = None

    reply: Optional[Callable[[str], None]] = None   # worker เรียกพร้อมผลลัพธ์ → ตอบกลับแหล่งเดิม
    sinks: list[str] = field(default_factory=list)  # ชื่อ sink เสริมที่จะส่งผลไปด้วย
    meta: dict[str, Any] = field(default_factory=dict)  # ข้อมูลเพิ่มให้ sink/reply ใช้ (แล้วแต่งาน)
