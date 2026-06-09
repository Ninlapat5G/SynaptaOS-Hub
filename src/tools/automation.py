"""
automation — เครื่องยนต์งานอัตโนมัติ "ของ Hub เอง" (แยกหน้าที่จากฝั่ง App)

ทำไมต้องแยก: บางงานทำได้แค่บนคอม — เขียน/รัน script, งานหนัก, หรือ
"สั่งงานแล้วเฝ้ารอจนเสร็จ" ก่อนค่อยรายงานกลับ. ฝั่ง App ดูแล routine บ้าน/IoT/มือถือ,
ฝั่ง Hub ดูแลงานคอมที่ตั้งเวลา/หน่วงเวลา/ทำซ้ำ

กลไก: เก็บงานลงไฟล์ (data/hub_jobs.json) → เธรด scheduler เคาะทุก ~5 วิ → ถึงเวลา
  → โยนงานเข้า pipeline pool (worker ที่แชร์กับ run_task) → agent ทำ → รายงานผลกลับแอปเจ้าของผ่าน FCM
  (เข้า pool = concurrency คุมรวมที่เดียว ไม่ spawn thread เองทุกงานจนถล่ม DGX)

trigger 3 แบบ:
  - delay : รันครั้งเดียวอีก N วินาที
  - at    : รันครั้งเดียวที่เวลา ISO (เช่น 2026-06-07T18:30)
  - every : รันซ้ำทุก N วินาที
"""

import json
import logging
import threading
import time
import uuid
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
    """โยนงานเข้า pipeline pool (ไม่รันเอง/ไม่ spawn thread) → worker รัน agent + รายงานผลกลับผ่าน reply"""
    import pipeline
    from pipeline.task import AgentTask
    from tools import account

    name, uid = job["name"], job["user_id"]

    def report(result: str) -> None:
        # reply = แจ้งผลกลับแอปเจ้าของ (ไม่รอผลตอบ — เป็นการแจ้ง ไม่ใช่ขอให้ทำต่อ)
        if uid:
            account.send_app_command(
                uid, f"งานอัตโนมัติ «{name}» ทำเสร็จแล้ว: {result}",
                "chat", sender=config.AGENT_NAME, wait=False,
            )
        _log.info("[job:%s] เสร็จ: %s", name, str(result)[:80])

    # block=False → คิวเต็มก็ไม่บล็อก scheduler (ข้ามรอบนี้ · งาน every จะลองใหม่รอบหน้า)
    ok = pipeline.submit(AgentTask(
        task=job["task"], user_id=uid or None, source="automation",
        history=[],          # งานอัตโนมัติ ไม่ยุ่ง session แชทของผู้ใช้ · allow_power=False (ดีฟอลต์)
        reply=report,
    ), block=False)
    if ok:
        _log.info("[job:%s] เข้า pool: %s", name, job["task"][:80])
    else:
        _log.warning("[job:%s] pool คิวเต็ม — ข้ามรอบนี้", name)


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
            "id": f"job-{uuid.uuid4().hex[:10]}",   # uuid กัน id ชน (เดิม epoch+len ชนได้ในวินาทีเดียวกัน)
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
