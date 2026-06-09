"""
values — อ่าน "ค่าปัจจุบัน" ของแหล่งที่ใช้เป็นเงื่อนไขในกฎ แล้วเทียบกับเป้าหมาย

แหล่ง (source) ที่รองรับ:
  "<topic>"        — ค่าสถานะอุปกรณ์ล่าสุด (จาก device_state ที่ sub MQTT)
  "online:<topic>" — อุปกรณ์ยัง "ออนไลน์" ไหม → "online" / "offline" (ดูจากเวลาที่เห็นล่าสุด)
  "__time__"       — เวลาของวัน "HH:MM"
  "__weekday__"    — วันในสัปดาห์ (mon..sun)
  "__battery__"    — แบตมือถือเจ้าของ (%) จาก telemetry
  "__charging__"   — กำลังชาร์จไหม "true"/"false"

หมายเหตุ: __battery__/__charging__ ต้องมี user_id (เป็นค่าของคน) · online/time/weekday คำนวณเอง
"""
import datetime
import time

# อุปกรณ์ที่ไม่ส่งสถานะมานานเกินนี้ (วินาที) ถือว่า offline
# (Node publish retained หมดอายุ ~5 นาที — ใช้ค่าเดียวกันให้สอดคล้อง)
ONLINE_TTL = 300

_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _to_min(hm: str) -> float:
    """'HH:MM' → จำนวนนาทีตั้งแต่เที่ยงคืน (เทียบเวลาได้ตรงกว่าเทียบ string)"""
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def get(source: str, user_id: str | None) -> str | None:
    """ค่าปัจจุบันของแหล่งเงื่อนไข (None = ยังไม่รู้)"""
    if source == "__time__":
        return datetime.datetime.now().strftime("%H:%M")
    if source == "__weekday__":
        return _WEEKDAYS[datetime.datetime.now().weekday()]
    if source in ("__battery__", "__charging__"):
        if not user_id:
            return None
        import store
        phone = store.load_part(user_id, "phone") or {}
        if source == "__battery__":
            lv = phone.get("level")
            return str(lv) if lv is not None else None
        return "true" if phone.get("charging") else "false"
    if source.startswith("online:"):
        import device_state
        ts = device_state.last_seen(source[len("online:"):])
        if ts is None:
            return "offline"
        return "online" if (time.time() - ts) < ONLINE_TTL else "offline"
    # ปกติ = topic อุปกรณ์
    import device_state
    return device_state.get(source)


def _cmp_num(cur: float, op: str, target: float) -> bool:
    return {
        ">": cur > target, "<": cur < target, ">=": cur >= target,
        "<=": cur <= target, "==": cur == target, "!=": cur != target,
    }.get(op, False)


def matches(cond: dict, user_id: str | None) -> bool:
    """เงื่อนไข 1 ข้อเป็นจริงตอนนี้ไหม"""
    source = cond.get("source", "")
    op = cond.get("op", "==")
    target = cond.get("value", "")
    cur = get(source, user_id)
    if cur is None:
        return False
    if op == "change":   # ในโมเดล level-based "change" = มีค่าอยู่ก็ถือว่าจริง (ใช้ร่วม edge)
        return True
    if source == "__weekday__":
        days = [d.strip().lower() for d in str(target).split(",") if d.strip()]
        return cur in days if op in ("==", "in") else cur not in days
    if source == "__time__":
        return _cmp_num(_to_min(cur), op, _to_min(str(target)))
    # ลองเทียบเป็นตัวเลขก่อน (sensor/แบต) — ไม่ใช่ตัวเลขค่อยเทียบ string
    try:
        return _cmp_num(float(cur), op, float(target))
    except (TypeError, ValueError):
        if op == "==":
            return str(cur) == str(target)
        if op == "!=":
            return str(cur) != str(target)
        return False
