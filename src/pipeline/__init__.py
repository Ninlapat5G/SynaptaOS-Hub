"""
pipeline — โครงรับงานจาก "แหล่งต่าง ๆ" → agent → "output หลายปลายทาง"

ส่วนประกอบ:
  - executor.py : thread pool + task queue (แกน concurrency, bounded + backpressure)
  - task.py     : AgentTask (หน่วยงาน 1 ชิ้น)
  - sources.py  : Source base class + registry (แหล่งป้อนงานแบบ listener — MQTT/file/timer ฯลฯ)
  - sinks.py    : Sink base class + registry (ปลายทาง output — log/fcm/...)
  - (source แบบ request เช่น HTTP อยู่ใน api/pipeline.py เรียก submit()/run_sync() ตรง ๆ)

เพิ่มของใหม่:
  - sink ใหม่   : subclass Sink + register_sink()  (ดู sinks.py)
  - source ใหม่ : subclass Source + register_source(...) ใน start() ด้านล่าง (ดู sources.py)

วิธีใช้จากที่อื่น:
  - pipeline.run_sync(task, user_id=...) → รอผล (เช่น run_task ของ MCP)
  - pipeline.submit(AgentTask(...))      → fire-and-forget, ผลไปออกที่ reply/sinks ของ task
"""
import logging

import config
from .task import AgentTask
from .executor import AgentExecutor
from . import sinks, sources

_log = logging.getLogger("pipeline")
_executor: AgentExecutor | None = None


def start() -> None:
    global _executor
    if _executor:
        return
    sinks.register_builtins()
    _executor = AgentExecutor(workers=config.AGENT_WORKERS, queue_max=config.AGENT_QUEUE_MAX)
    _executor.start()

    # ── เปิดใช้ listener source ตรงนี้ (ดูแม่แบบใน sources.py) ──
    # ตัวอย่าง: sources.register_source(sources.ExampleIntervalSource(every_sec=3600))
    for src in sources.all_sources():
        try:
            src.start(submit)
        except Exception as e:
            _log.error("source '%s' start ล้มเหลว: %s", src.name, e)
    _log.info("pipeline พร้อมทำงาน")


def stop() -> None:
    for src in sources.all_sources():
        try:
            src.stop()
        except Exception:
            pass
    if _executor:
        _executor.stop()


def submit(task: AgentTask, block: bool = True, timeout: float | None = 5.0) -> bool:
    """ใส่งานเข้า queue (fire-and-forget) — ผลไปออกที่ task.reply / task.sinks"""
    if not _executor:
        _log.warning("submit ก่อน pipeline.start()")
        return False
    return _executor.submit(task, block=block, timeout=timeout)


def run_sync(task: str, user_id: str | None = None, allow_power: bool = False,
             source: str = "sync", history: list | None = None,
             sinks: list[str] | None = None, timeout: float = 180.0) -> str:
    """ส่งงานเข้า pool แล้วรอผล (สำหรับผู้เรียกที่ต้องการคำตอบกลับ)"""
    if not _executor:
        return "[pipeline ยังไม่พร้อม]"
    return _executor.run_sync(task, user_id=user_id, allow_power=allow_power,
                              source=source, history=history, sinks=sinks, timeout=timeout)


def dispatch_sink(name: str, task: AgentTask, result: str) -> None:
    """ส่งผลเข้า sink ตามชื่อ (ใช้ตอนอยากยิง sink เพิ่มเองนอก worker)"""
    sinks.dispatch(name, task, result)
