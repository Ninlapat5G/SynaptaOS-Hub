"""
AgentExecutor — แกน concurrency: thread pool + task queue (แบบจำกัดขนาด)

ทำไม thread (ไม่ใช่ process): งาน agent เป็น I/O-bound (รอ LLM ที่ DGX / MQTT / subprocess)
→ thread ขนานงานได้เต็มที่ และ "แชร์ session/store/MQTT client ได้ตรง ๆ" โดยไม่ต้องทำ IPC

DGX เสิร์ฟ gemma แบบขนานได้จริง (Ollama OLLAMA_NUM_PARALLEL = 8 slot, ไม่ใช่ทำทีละอัน) แต่ DGX
แชร์กันหลาย Hub ในบ้าน → AGENT_WORKERS = "เพดานต่อ Hub" (ดีฟอลต์ 4) เผื่อ slot ให้ Hub อื่น
เกินเพดานก็จ่อคิวไป (ดู config.AGENT_WORKERS)

queue แบบจำกัดขนาด = มี backpressure: งานท่วม → ผู้ส่งรอคิว/ถูกปฏิเสธ
ไม่ใช่ spawn thread ไม่จำกัดจนเครื่อง/DGX ล้ม (หลาย user พร้อมกันจึงลื่นและคุมได้)
"""
import logging
import queue
import threading

from .task import AgentTask
from . import sinks as _sinks

_log = logging.getLogger("pipeline.executor")


class AgentExecutor:
    def __init__(self, workers: int = 4, queue_max: int = 100):
        self._q: "queue.Queue[AgentTask | None]" = queue.Queue(maxsize=queue_max)
        self._n = workers
        self._threads: list[threading.Thread] = []
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self._n):
            t = threading.Thread(target=self._loop, name=f"agent-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        _log.info("executor เริ่มทำงาน (%d workers, queue สูงสุด %d)", self._n, self._q.maxsize)

    def stop(self) -> None:
        self._running = False
        for _ in self._threads:            # ใส่ sentinel ปลุกทุก worker ให้ตื่นมาเห็นแล้วจบ
            try:
                self._q.put_nowait(None)
            except queue.Full:
                pass

    def submit(self, task: AgentTask, block: bool = True, timeout: float | None = 5.0) -> bool:
        """ใส่งานเข้า queue (fire-and-forget) — คืน False ถ้า queue เต็มภายใน timeout"""
        try:
            self._q.put(task, block=block, timeout=timeout)
            return True
        except queue.Full:
            _log.warning("queue เต็ม — ปฏิเสธงานจาก '%s'", task.source)
            return False

    def run_sync(self, task: str, user_id: str | None = None, allow_power: bool = False,
                 source: str = "sync", history: list | None = None,
                 sinks: list[str] | None = None, timeout: float = 180.0) -> str:
        """ส่งงานเข้า pool แล้ว 'รอผล' — สำหรับผู้เรียกที่ต้องการคำตอบกลับ (run_task / HTTP wait)

        history=None → agent ใช้ session memory ของ user (บทสนทนาต่อเนื่อง)
        sinks → ส่งผลเข้า sink เสริมด้วย (นอกจากคืนค่ากลับผู้เรียก)
        """
        done = threading.Event()
        holder = {"result": ""}

        def _reply(result: str) -> None:
            holder["result"] = result
            done.set()

        t = AgentTask(task=task, user_id=user_id, allow_power=allow_power, source=source,
                      history=history, reply=_reply, sinks=sinks or [])
        if not self.submit(t):
            return "ระบบกำลังยุ่งมากค่ะ ลองอีกครั้งสักครู่นะคะ 🙏"
        if not done.wait(timeout):
            return "งานนี้ใช้เวลานานเป็นพิเศษ ยังทำอยู่เบื้องหลังค่ะ"
        return holder["result"]

    def _loop(self) -> None:
        import agent
        while self._running:
            task = self._q.get()
            try:
                if task is None:           # sentinel ตอน stop
                    break
                try:
                    result = agent.run(task.task, user_id=task.user_id,
                                       allow_power=task.allow_power, history=task.history)
                except Exception as e:
                    _log.error("worker รันงานล้มเหลว: %s", e)
                    result = f"[error] {e}"
                # ส่ง output: (1) reply กลับแหล่งเดิม  (2) sink เสริมที่ task ระบุ — ใช้พร้อมกันได้
                if task.reply:
                    try:
                        task.reply(result)
                    except Exception as e:
                        _log.error("reply กลับแหล่ง '%s' ล้มเหลว: %s", task.source, e)
                for name in task.sinks:
                    _sinks.dispatch(name, task, result)
            finally:
                self._q.task_done()
