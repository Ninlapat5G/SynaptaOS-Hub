"""
rules — ที่เก็บกฎ event-driven ของ Hub (โหลด/เซฟ/เพิ่ม/ลบ) + MCP tools ให้ตั้งกฎได้

กฎเก็บไฟล์ data/event_rules.json · การ "ประเมิน+ยิง" อยู่ที่ engine.py (แยกหน้าที่กัน)

โครงกฎ (1 กฎ):
{
  "id": "...", "user_id": "...", "name": "...", "enabled": true,
  "logic": "AND",                                  # AND | OR (รวมหลายเงื่อนไข)
  "conditions": [ {"source": "...", "op": "...", "value": "..."}, ... ],
  "actions":    [ {"kind": "device|scene|notify|agent", ...}, ... ],
  "cooldown_sec": 60, "once": false
}
source ของเงื่อนไข + ชนิด action ดู events/values.py และ events/actions.py
"""
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Literal

import config

_log = logging.getLogger("events.rules")

_FILE = Path(config.DATA_DIR) / "event_rules.json"
_lock = threading.Lock()
_rules: list[dict] = []


def load() -> None:
    global _rules
    try:
        _rules = json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        _rules = []


def _save() -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_rules, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_FILE)


def snapshot() -> list[dict]:
    """สำเนากฎปัจจุบัน (engine วนอ่านได้โดยไม่ชน lock ตอนแก้)"""
    with _lock:
        return list(_rules)


def add(rule: dict) -> None:
    with _lock:
        _rules.append(rule)
        _save()


def remove(rule_id: str) -> bool:
    with _lock:
        before = len(_rules)
        _rules[:] = [r for r in _rules if r.get("id") != rule_id]
        removed = before - len(_rules)
        if removed:
            _save()
    return bool(removed)


def disable(rule_id: str) -> None:
    """ปิดกฎ (ใช้กับ once=true หลังยิงไปแล้ว)"""
    with _lock:
        for r in _rules:
            if r.get("id") == rule_id:
                r["enabled"] = False
        _save()


def _new_id() -> str:
    # uuid กัน id ชนกัน — แบบเดิม (epoch+len) สร้าง 2 กฎในวินาทีเดียวกันได้ id ซ้ำ
    return f"rule-{uuid.uuid4().hex[:10]}"


# ── MCP tools — ให้ฝั่ง App (hub_agent)/admin ตั้งกฎได้ ───────────────────────
def register(mcp):
    @mcp.tool()
    def add_rule(source: str, op: str, value: str,
                 action_kind: Literal["device", "scene", "notify", "agent"],
                 user_id: str = "", name: str = "",
                 device_topic: str = "", device_value: str = "", scene_id: str = "",
                 text: str = "", task: str = "",
                 cooldown_sec: int = 60, once: bool = False) -> str:
        """ตั้งกฎอัตโนมัติ "เงื่อนไขเดียว → ทำ 1 อย่าง" (เคสที่ใช้บ่อยสุด)
        - source: topic อุปกรณ์ (เช่น 'bedroom/temp') หรือแหล่งพิเศษ '__time__' (HH:MM), '__weekday__' (mon..sun), '__battery__' (%), '__charging__', 'online:<topic>' (online/offline)
        - op: '>' '<' '>=' '<=' '==' '!=' (เทียบค่า)
        - action_kind='device' ใส่ device_topic+device_value | 'scene' ใส่ scene_id | 'notify' ใส่ text (เด้งแจ้งเจ้าของ) | 'agent' ใส่ task (ให้ AI คิด+ทำ+รายงาน)
        - cooldown_sec: กันยิงรัวกี่วินาที · once=true: ทำครั้งเดียวแล้วปิดกฎ
        ตัวอย่าง: ห้องนอนเกิน 30 องศาเปิดแอร์ → source='bedroom/temp', op='>', value='30', action_kind='device', device_topic='bedroom/ac', device_value='true'
        กฎหลายเงื่อนไข (AND/OR) หรือหลาย action ให้ใช้ add_advanced_rule แทน"""
        action: dict = {"kind": action_kind}
        if action_kind == "device":
            action.update(topic=device_topic, value=device_value)
        elif action_kind == "scene":
            action["scene_id"] = scene_id
        elif action_kind == "notify":
            action["text"] = text
        elif action_kind == "agent":
            action["task"] = task
        rule = {
            "id": _new_id(), "user_id": user_id, "name": name or f"{source} {op} {value}",
            "enabled": True, "logic": "AND",
            "conditions": [{"source": source, "op": op, "value": value}],
            "actions": [action], "cooldown_sec": cooldown_sec, "once": once,
        }
        add(rule)
        return f"ตั้งกฎ «{rule['name']}» แล้วค่ะ · id={rule['id']}"

    @mcp.tool()
    def add_advanced_rule(rule_json: str) -> str:
        """ตั้งกฎซับซ้อน (หลายเงื่อนไข AND/OR หรือหลาย action) ด้วย JSON ตรง ๆ
        rule_json = {"user_id","name","logic":"AND|OR","conditions":[{"source","op","value"}],"actions":[{"kind",...}],"cooldown_sec","once"}
        - condition.source: topic อุปกรณ์ / '__time__' / '__weekday__' / '__battery__' / '__charging__' / 'online:<topic>'
        - action.kind: 'device'{topic,value} | 'scene'{scene_id} | 'notify'{text} | 'agent'{task}
        ตัวอย่าง: หลัง 18:00 และห้องนั่งเล่นมืด → เปิดไฟ:
        {"user_id":"u1","name":"ค่ำแล้วเปิดไฟ","logic":"AND","conditions":[{"source":"__time__","op":">=","value":"18:00"},{"source":"living/lux","op":"<","value":"100"}],"actions":[{"kind":"scene","scene_id":"evening"}],"cooldown_sec":600}"""
        try:
            data = json.loads(rule_json)
        except Exception as e:
            return f"JSON ไม่ถูกต้อง: {e}"
        if not data.get("conditions") or not data.get("actions"):
            return "ต้องมีทั้ง conditions และ actions อย่างน้อยอย่างละ 1"
        rule = {
            "id": _new_id(),
            "user_id": data.get("user_id", ""), "name": data.get("name", "") or _new_id(),
            "enabled": True, "logic": (data.get("logic") or "AND").upper(),
            "conditions": data["conditions"], "actions": data["actions"],
            "cooldown_sec": data.get("cooldown_sec", 60), "once": bool(data.get("once", False)),
        }
        add(rule)
        return f"ตั้งกฎ «{rule['name']}» แล้วค่ะ ({len(rule['conditions'])} เงื่อนไข, {len(rule['actions'])} action) · id={rule['id']}"

    @mcp.tool()
    def list_rules(user_id: str = "") -> str:
        """ดูกฎอัตโนมัติที่ตั้งไว้ (เว้น user_id ว่าง = ดูทุกคน)"""
        rows = [r for r in snapshot() if not user_id or r.get("user_id") == user_id]
        if not rows:
            return "(ยังไม่มีกฎ)"
        out = []
        for r in rows:
            off = "" if r.get("enabled", True) else " [ปิดอยู่]"
            conds = f" {r.get('logic', 'AND')} ".join(
                f"{c.get('source')} {c.get('op')} {c.get('value')}" for c in r.get("conditions", []))
            acts = ", ".join(a.get("kind", "?") for a in r.get("actions", []))
            out.append(f"- {r.get('name')}{off}: ({conds}) → {acts} · id={r.get('id')}")
        return "\n".join(out)

    @mcp.tool()
    def remove_rule(rule_id: str) -> str:
        """ลบกฎอัตโนมัติตาม id"""
        return "ลบกฎแล้วค่ะ" if remove(rule_id) else f"ไม่พบกฎ id={rule_id}"
