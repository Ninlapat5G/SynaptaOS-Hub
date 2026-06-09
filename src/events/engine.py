"""
engine — หัวใจประเมินกฎ: ทุก event (หรือทุก tick) → เช็คกฎที่เข้าเงื่อนไข → ยิง action

โมเดล "level-based + edge":
- ประเมินเงื่อนไขทั้งหมดของกฎกับ "ค่าปัจจุบัน" (values.matches) แล้วรวมด้วย AND/OR
- ยิงตอน "ข้ามขอบ" (false→true) ครั้งเดียว · กลับมายิงใหม่เมื่อหลุดเงื่อนไขแล้วเข้าใหม่
- cooldown กันยิงรัว · once = ยิงครั้งเดียวแล้วปิดกฎ

ทำไมมี tick: เงื่อนไขที่ไม่มี event มาปลุก (เวลา/วัน/อุปกรณ์ออฟไลน์) ต้องเคาะเองเป็นระยะ
ส่วนค่าอุปกรณ์/แบตที่เปลี่ยน จะถูกปลุกทันทีผ่าน bus (device_state/telemetry publish เข้ามา)
"""
import logging
import threading
import time

from . import actions, bus, rules, values

_log = logging.getLogger("events.engine")

TICK_SEC = 30                       # เคาะประเมินเงื่อนไขเวลา/ออฟไลน์ทุก ๆ กี่วินาที
_armed: dict[str, bool] = {}        # rule_id → เงื่อนไขรวมเป็นจริงค้างอยู่ไหม (สำหรับ edge)
_last_fire: dict[str, float] = {}   # rule_id → เวลายิงล่าสุด (สำหรับ cooldown)
_wake = threading.Event()           # event เข้า → ปลุก worker (ประเมิน/ยิงทำใน thread ของ engine เอง)
_stop = threading.Event()


def _combined(rule: dict) -> bool:
    conds = rule.get("conditions", [])
    if not conds:
        return False
    uid = rule.get("user_id") or None
    results = [values.matches(c, uid) for c in conds]
    return any(results) if rule.get("logic", "AND").upper() == "OR" else all(results)


def _fire(rule: dict) -> None:
    name = rule.get("name") or rule.get("id")
    uid = rule.get("user_id") or None
    for action in rule.get("actions", []):
        try:
            _log.info("[rule:%s] %s → %s", name, action.get("kind"), actions.run(action, uid))
        except Exception as e:
            _log.error("[rule:%s] action ล้มเหลว: %s", name, e)
    if rule.get("once"):
        rules.disable(rule.get("id", ""))


def _evaluate_all() -> None:
    now = time.time()
    for rule in rules.snapshot():
        # try ต่อกฎ — กฎเสีย 1 ข้อ (เช่น value เวลาไม่ใช่ HH:MM, cooldown_sec เป็น null)
        # ต้องไม่ทำให้กฎที่เหลือไม่ถูกประเมินไปด้วยทั้งรอบ
        try:
            if not rule.get("enabled", True):
                continue
            rid = rule.get("id", "")
            if not _combined(rule):
                _armed[rid] = False                 # หลุดเงื่อนไข → พร้อมยิงรอบหน้า
                continue
            if _armed.get(rid):                     # edge: เข้าเงื่อนไขค้างอยู่แล้ว ไม่ยิงซ้ำ
                continue
            if now - _last_fire.get(rid, 0) < float(rule.get("cooldown_sec") or 0):
                continue                            # ติด cooldown — ยังไม่ arm → พ้นแล้วถ้ายังจริงอยู่จะยิงรอบถัดไป (เลื่อน ไม่ใช่ทิ้ง)
            _armed[rid] = True
            _last_fire[rid] = now
            _fire(rule)
        except Exception as e:
            _log.error("กฎ %s ประเมินผิดพลาด (ข้ามเฉพาะกฎนี้): %s", rule.get("id") or rule.get("name"), e)


def _on_event(ev) -> None:
    # ห้ามประเมิน/ยิง action ใน thread ของผู้ส่ง (เป็น thread เครือข่ายของ MQTT) — แค่ปลุก worker
    _wake.set()


def _loop() -> None:
    """worker เดียวของ engine: ตื่นเมื่อมี event หรือครบ tick แล้วประเมินกฎทั้งหมด"""
    while not _stop.is_set():
        _wake.wait(TICK_SEC)
        _wake.clear()
        if _stop.is_set():
            break
        try:
            _evaluate_all()
        except Exception as e:
            _log.error("ประเมินกฎผิดพลาด: %s", e)


def start() -> None:
    rules.load()
    bus.subscribe(_on_event)
    threading.Thread(target=_loop, name="events-engine", daemon=True).start()
    _log.info("rule engine เริ่มทำงาน (%d กฎ, tick ทุก %ds)", len(rules.snapshot()), TICK_SEC)


def stop() -> None:
    _stop.set()
    _wake.set()   # ปลุกให้ worker เห็น _stop แล้วจบ
