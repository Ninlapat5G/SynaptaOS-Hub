"""
session — ความจำบทสนทนาชั่วคราวต่อผู้ใช้ (เก็บใน RAM, หมดอายุเองเมื่อเงียบนานเกินกำหนด)

ทำไมต้องมี: run_task ที่ App ยิงมาไม่ได้แนบประวัติมาด้วย → ถ้าไม่เก็บเอง Hub จะลืมทุกครั้ง
สั่ง "เปิดเพลง" แล้วสั่งต่อ "ดังกว่านี้" จะไม่รู้ว่าหมายถึงอะไร

เก็บแยกตาม user_id (ของใครของมัน) + ล้างทิ้งเมื่อไม่มีความเคลื่อนไหวเกิน TTL
(กัน RAM บวม + กันบทสนทนาคนละเรื่อง/คนละช่วงเวลามาปนกัน)
"""

import threading
import time

_TTL = 1800   # เงียบเกิน 30 นาที = ล้าง session ทิ้ง
_MAX = 10     # เก็บข้อความล่าสุดกี่ข้อความ (พอให้จำบริบท ไม่บวม)

_lock = threading.Lock()
_sessions: dict[str, dict] = {}   # user_id -> {"msgs": [{"role","text"}...], "ts": epoch}


def _prune() -> None:
    """ลบ session ที่เงียบนานเกิน TTL (เรียกใต้ _lock แล้ว)"""
    now = time.time()
    for uid in [u for u, s in _sessions.items() if now - s["ts"] > _TTL]:
        del _sessions[uid]


def get(user_id: str | None) -> list:
    """คืนประวัติบทสนทนาล่าสุดของผู้ใช้คนนี้ (ลิสต์ {role, text}) — ว่างถ้าไม่มี/หมดอายุ"""
    if not user_id:
        return []
    with _lock:
        _prune()
        s = _sessions.get(user_id)
        return list(s["msgs"]) if s else []


def append(user_id: str | None, role: str, text: str) -> None:
    """ต่อท้ายข้อความ 1 ข้อความ (role = 'user' หรือ 'agent') แล้วรีเฟรชเวลาล่าสุด"""
    text = (text or "").strip()
    if not user_id or not text:
        return
    with _lock:
        s = _sessions.setdefault(user_id, {"msgs": [], "ts": 0})
        s["msgs"].append({"role": role, "text": text})
        s["msgs"] = s["msgs"][-_MAX:]
        s["ts"] = time.time()
