"""
automation — เครื่องยนต์งานอัตโนมัติ "ของ Hub เอง" (แยกหน้าที่จากฝั่ง App)

ทำไมต้องแยก: บางงานทำได้แค่บนคอม — เขียน/รัน script, งานหนัก, หรือ
"สั่งงานแล้วเฝ้ารอจนเสร็จ" ก่อนค่อยรายงานกลับ. ฝั่ง App ดูแล routine บ้าน/IoT/มือถือ,
ฝั่ง Hub ดูแลงานคอมที่ตั้งเวลา/หน่วงเวลา/ทำซ้ำ

กลไก: เก็บงานลงไฟล์ (data/hub_jobs.json) → เธรด scheduler เคาะทุก ~5 วิ → ถึงเวลา
  → รันงานผ่าน agent ของ Hub (เขียน code/รัน script ได้) → รายงานผลกลับแอปเจ้าของผ่าน FCM

trigger 3 แบบ:
  - delay : รันครั้งเดียวอีก N วินาที
  - at    : รันครั้งเดียวที่เวลา ISO (เช่น 2026-06-07T18:30)
  - every : รันซ้ำทุก N วินาที
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

import config

_log = logging.getLogger("automation")

_FILE = Path(config.DATA_DIR) / "hub_jobs.json"
_lock = threading.Lock()
_jobs: list[dict] = []          # [{id,user_id,name,mode,value,task,next_run,enabled}]
_thread: threading.Thread | None = None
_stop = threading.Event()


def _load() -> None:
    global _jobs
    try:
        _jobs = json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        _jobs = []


def _save() -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_FILE)


def _next_run(mode: str, value: str) -> float:
    """คำนวณเวลารันรอบถัดไป (epoch) จาก mode/value"""
    now = time.time()
    if mode == "delay" or mode == "every":
        return now + float(value)
    if mode == "at":
        return datetime.fromisoformat(value).timestamp()
    raise ValueError(f"mode ไม่ถูกต้อง: {mode}")


def _fire(job: dict) -> None:
    """รันงาน 1 ตัวในเธรดแยก → รายงานผลกลับแอปเจ้าของ (ไม่บล็อก scheduler)"""
    import agent
    from tools import account

    def work():
        _log.info("[job:%s] รัน: %s", job["name"], job["task"][:80])
        try:
            # history=[] → ไม่ดึง/ไม่เขียน session แชทของผู้ใช้ (งานอัตโนมัติแยกจากบทสนทนา)
            result = agent.run(job["task"], user_id=job["user_id"] or None, history=[])  # allow_power=False
        except Exception as e:
            result = f"[error] {e}"
        # รายงานกลับแอปเจ้าของแบบไม่รอผลตอบ (เป็นการแจ้งผล ไม่ใช่ขอให้ทำต่อ)
        if job["user_id"]:
            account.send_app_command(
                job["user_id"],
                f"งานอัตโนมัติ «{job['name']}» ทำเสร็จแล้ว: {result}",
                "chat", sender=config.AGENT_NAME, wait=False,
            )
        _log.info("[job:%s] เสร็จ: %s", job["name"], str(result)[:80])

    threading.Thread(target=work, daemon=True).start()


def _tick() -> None:
    now = time.time()
    fired = []
    with _lock:
        for job in _jobs:
            if job.get("enabled") and now >= job.get("next_run", 0):
                fired.append(job)
                if job["mode"] == "every":
                    job["next_run"] = now + float(job["value"])   # รอบถัดไป
                else:
                    job["enabled"] = False                        # ครั้งเดียวจบ
        # ลบงานครั้งเดียวที่ทำไปแล้วออก ให้ลิสต์สะอาด
        if fired:
            _jobs[:] = [j for j in _jobs if j.get("enabled") or j["mode"] == "every"]
            _save()
    for job in fired:
        _fire(job)


def _loop() -> None:
    while not _stop.wait(5):   # เคาะทุก 5 วิ
        try:
            _tick()
        except Exception as e:
            _log.error("scheduler tick ผิดพลาด: %s", e)


def start() -> None:
    global _thread
    _load()
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    _log.info("automation scheduler เริ่มทำงาน (%d งานค้างอยู่)", len(_jobs))


def stop() -> None:
    _stop.set()


# ── MCP tools — ให้ฝั่ง App (hub_agent) สั่งตั้ง/ดู/ยกเลิกงานได้ ────────────────
def register(mcp):
    @mcp.tool()
    def schedule_task(task: str, mode: Literal["delay", "at", "every"], value: str,
                      user_id: str = "", name: str = "") -> str:
        """ตั้งงานให้ Hub ทำตามเวลา (เหมาะกับงานคอม เช่น รัน script, งานหนัก, ทำตามกำหนด).
        - task: คำสั่งภาษาคนที่ให้ Hub ทำ เช่น 'รัน backup.py แล้วบอกผลลัพธ์'
        - mode='delay' value=วินาที (อีกกี่วิรันครั้งเดียว) | mode='at' value=เวลา ISO เช่น '2026-06-07T18:30' (รันครั้งเดียว) | mode='every' value=วินาที (ทำซ้ำทุก N วิ)
        - user_id: รหัสแอปเจ้าของงาน (Hub จะรายงานผลกลับให้คนนี้เมื่อทำเสร็จ)
        เมื่อทำเสร็จ Hub จะเด้งแจ้งผลกลับไปที่แอปเจ้าของเองค่ะ"""
        try:
            nr = _next_run(mode, value)
        except Exception as e:
            return f"ตั้งงานไม่ได้: {e}"
        job = {
            "id": f"job-{int(time.time())}-{len(_jobs)}",
            "user_id": user_id, "name": name or task[:30], "mode": mode,
            "value": value, "task": task, "next_run": nr, "enabled": True,
        }
        with _lock:
            _jobs.append(job)
            _save()
        when = datetime.fromtimestamp(nr).strftime("%Y-%m-%d %H:%M:%S")
        repeat = f" (ทำซ้ำทุก {value} วิ)" if mode == "every" else ""
        return f"ตั้งงาน «{job['name']}» แล้ว จะเริ่ม {when}{repeat} · id={job['id']}"

    @mcp.tool()
    def list_scheduled_tasks(user_id: str = "") -> str:
        """ดูงานอัตโนมัติของ Hub ที่ตั้งไว้ (เว้น user_id ว่าง = ดูทุกคน)"""
        with _lock:
            rows = [j for j in _jobs if not user_id or j["user_id"] == user_id]
            out = []
            for j in rows:
                when = datetime.fromtimestamp(j["next_run"]).strftime("%m-%d %H:%M")
                out.append(f"- {j['name']} [{j['mode']}] รอบหน้า {when} · id={j['id']} · {j['task'][:50]}")
        return "\n".join(out) if out else "(ยังไม่มีงานตั้งไว้)"

    @mcp.tool()
    def cancel_scheduled_task(job_id: str) -> str:
        """ยกเลิก/ลบงานอัตโนมัติของ Hub ตาม id"""
        with _lock:
            before = len(_jobs)
            _jobs[:] = [j for j in _jobs if j["id"] != job_id]
            removed = before - len(_jobs)
            if removed:
                _save()
        return "ยกเลิกงานแล้วค่ะ" if removed else f"ไม่พบงาน id={job_id}"
