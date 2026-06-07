"""
Sink — ปลายทางรับ "ผลลัพธ์" ของ agent (output)

เพิ่ม sink ใหม่:
    1. สร้าง subclass ของ Sink (ตั้ง name + เขียน send)
    2. register_sink(MySink())  (ทำใน register_builtins() ด้านล่าง หรือที่ pipeline.start())
จากนั้น task อ้าง sink ด้วยชื่อใน AgentTask.sinks เช่น sinks=['fcm', 'log']
"""
import logging
from abc import ABC, abstractmethod

_log = logging.getLogger("pipeline.sink")


class Sink(ABC):
    name: str = "sink"

    @abstractmethod
    def send(self, task, result: str) -> None:
        """ส่งผลลัพธ์ของ agent ไปยังปลายทางของ sink นี้"""


_SINKS: dict[str, Sink] = {}


def register_sink(sink: Sink) -> None:
    _SINKS[sink.name] = sink


def dispatch(name: str, task, result: str) -> None:
    """ส่งผลเข้า sink ตามชื่อ — sink ตัวเดียวล้มต้องไม่ทำให้ทั้ง pipeline พัง"""
    sink = _SINKS.get(name)
    if not sink:
        _log.warning("ไม่รู้จัก sink '%s' (มี: %s)", name, ", ".join(_SINKS) or "-")
        return
    try:
        sink.send(task, result)
    except Exception as e:
        _log.error("sink '%s' ล้มเหลว: %s", name, e)


# ── built-in sinks ────────────────────────────────────────────────────────────
class LogSink(Sink):
    """บันทึกผลลง log (ใช้ debug / งานที่ไม่ต้องส่งไปไหน)"""
    name = "log"

    def send(self, task, result: str) -> None:
        _log.info("[%s] %s → %s", task.source, task.task[:60], str(result)[:160])


class FcmSink(Sink):
    """ส่งผลกลับไปที่แอปมือถือของ user ผ่าน FCM (ต้องมี task.user_id)"""
    name = "fcm"

    def send(self, task, result: str) -> None:
        if not task.user_id:
            _log.warning("fcm sink ข้าม — task ไม่มี user_id")
            return
        from tools import account
        account.send_app_command(task.user_id, str(result), "chat", wait=False)


def register_builtins() -> None:
    register_sink(LogSink())
    register_sink(FcmSink())
