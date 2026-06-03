"""
store — ที่เก็บข้อมูลฝั่ง Hub แบบเป็นระเบียบ แยกไฟล์ แยก user (รองรับ multi-user)

โครง:
  {DATA_DIR}/
    registry.json                  ← ดัชนีรวม user ทั้งหมด (ดูเร็ว ไม่ต้องไล่เปิดทุกโฟลเดอร์)
    users/<user_id>/
      profile.json   kd.json   scenes.json   routines.json   phone.json

หลักการ: agent อ่านเฉพาะไฟล์ที่ต้องใช้ (load_part) → ไม่เปลือง context
ทุกไฟล์เป็น JSON เขียนแบบ atomic (เขียน tmp แล้ว replace) กันไฟล์พังถ้าไฟดับกลางคัน
"""

import json
import os
import re
import threading
import time
from pathlib import Path

import config

# ส่วนข้อมูลที่เก็บได้ — แอปจะ sync มาเฉพาะส่วนที่เปลี่ยน
PARTS = ("profile", "kd", "scenes", "routines", "phone")

_BASE = Path(config.DATA_DIR)
_REGISTRY = _BASE / "registry.json"
_lock = threading.Lock()


def _safe(user_id: str) -> str:
    """กัน path traversal — เหลือเฉพาะ a-z A-Z 0-9 _ - (อื่นๆ แทนด้วย _)"""
    s = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or "").strip())
    return s or "unknown"


def _user_dir(user_id: str) -> Path:
    return _BASE / "users" / _safe(user_id)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic บนทั้ง Windows และ Linux


def _update_registry(user_id: str, **fields) -> None:
    reg = _read_json(_REGISTRY) or {}
    entry = reg.get(user_id, {})
    entry.update(fields)
    entry["last_seen"] = int(time.time())
    reg[user_id] = entry
    _write_json(_REGISTRY, reg)


# ── API ──────────────────────────────────────────────────────────────────────
def register_user(user_id: str, app_name: str, profile: dict | None = None) -> dict:
    """จด user ใหม่ (หรืออัปเดตของเดิม) — สร้างโฟลเดอร์ + profile + ลง registry"""
    with _lock:
        d = _user_dir(user_id)
        first_time = not d.exists()
        prof = _read_json(d / "profile.json") or {}
        prof.update(profile or {})
        prof["app_name"] = app_name
        if first_time:
            prof["registered_at"] = int(time.time())
        _write_json(d / "profile.json", prof)
        _update_registry(user_id, app_name=app_name)
        return {"user_id": _safe(user_id), "new": first_time, "app_name": app_name}


def is_registered(user_id: str) -> bool:
    return (_user_dir(user_id) / "profile.json").exists()


def save_part(user_id: str, kind: str, data) -> None:
    """เก็บข้อมูล 1 ส่วน (kd/scenes/routines/phone/profile) เป็นไฟล์แยก"""
    if kind not in PARTS:
        raise ValueError(f"unknown part: {kind}")
    with _lock:
        _write_json(_user_dir(user_id) / f"{kind}.json", data)
        _update_registry(user_id)


def load_part(user_id: str, kind: str):
    """อ่านข้อมูล 1 ส่วน — ไม่มีคืน None (อ่านเฉพาะที่ต้องใช้ ประหยัด context)"""
    if kind not in PARTS:
        raise ValueError(f"unknown part: {kind}")
    return _read_json(_user_dir(user_id) / f"{kind}.json")


def list_users() -> dict:
    return _read_json(_REGISTRY) or {}
