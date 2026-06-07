"""
Source — แหล่งที่ "ป้อนงาน" ให้ agent ทำ (input)

มี 2 สไตล์ในระบบนี้:
  1) listener-style (ไฟล์นี้) — เปิดฟังค้างไว้แล้ว "push" งานเข้ามาเอง
     (เช่น MQTT topic, file-watch, ตั้งเวลา) → subclass Source + register_source()
     engine จะเรียก start(submit) ให้ตอน pipeline.start()
  2) request-style — มีคนยิงเข้ามาเป็นครั้ง ๆ (เช่น HTTP) → ทำเป็น REST endpoint ใน api/
     แล้วเรียก pipeline.submit() / pipeline.run_sync() ตรง ๆ (ดูตัวอย่าง api/pipeline.py)

submit(AgentTask) -> bool : ใส่งานเข้า queue (คืน False ถ้า queue เต็ม)
"""
import logging
import threading
from abc import ABC, abstractmethod
from typing import Callable

from .task import AgentTask

_log = logging.getLogger("pipeline.source")


class Source(ABC):
    name: str = "source"

    @abstractmethod
    def start(self, submit: Callable[[AgentTask], bool]) -> None:
        """เริ่มฟัง/รับงาน — เมื่อมีงานเข้า ให้เรียก submit(AgentTask)"""

    def stop(self) -> None:
        """เก็บกวาด (override ถ้าต้องปิด connection/thread)"""


_SOURCES: list[Source] = []


def register_source(src: Source) -> None:
    _SOURCES.append(src)


def all_sources() -> list[Source]:
    return list(_SOURCES)


# ─────────────────────────────────────────────────────────────────────────────
# แม่แบบ (template) — ก๊อปไปทำของจริง แล้ว register_source(...) ใน pipeline.start()
# ตัวนี้ "ไม่ถูกเปิดใช้" อัตโนมัติ เป็นแค่โครงให้เห็นว่า source 1 ตัวหน้าตาเป็นยังไง
# ─────────────────────────────────────────────────────────────────────────────
class ExampleIntervalSource(Source):
    """ตัวอย่าง listener source: ยิงงานเดิมซ้ำทุก N วินาที

    ทำของจริง: เปลี่ยน build_task() ให้ดึงข้อมูลจาก "แหล่งจริง" (เซ็นเซอร์/คิว/ไฟล์ ฯลฯ)
    แล้วเลือก output ผ่าน sinks/reply ของ AgentTask
    """

    name = "example_interval"

    def __init__(self, every_sec: float = 3600, user_id: str | None = None):
        self._every = every_sec
        self._user_id = user_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, submit: Callable[[AgentTask], bool]) -> None:
        def loop():
            while not self._stop.wait(self._every):
                submit(self.build_task())
        self._thread = threading.Thread(target=loop, name=f"src-{self.name}", daemon=True)
        self._thread.start()
        _log.info("%s เริ่มทำงาน (ทุก %ss)", self.name, self._every)

    def build_task(self) -> AgentTask:
        return AgentTask(
            task="สรุปสถานะระบบสั้น ๆ",
            user_id=self._user_id,
            source=self.name,
            history=[],          # งานอัตโนมัติ ไม่ยุ่ง session แชทของ user
            sinks=["log"],       # output ไปไหน — เลือกได้ต่อ task (log / fcm / ...)
        )

    def stop(self) -> None:
        self._stop.set()
