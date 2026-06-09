"""
brain — สมองของ Hub แบบ LlamaIndex Workflow (ชั้น B)

ทางเลือกแทน ReAct เดิม (agent.py) — เปิดใช้ด้วย config.BRAIN = "workflow"
agent.run จะแก้ session/ประวัติให้แล้วเรียก brain.run ที่นี่ (signature เข้ากันได้)

ระบบรอบนอกเหมือนเดิมหมด: pipeline pool, automation, A2A, MCP, events เรียกผ่าน agent.run ตัวเดียว
"""
import asyncio
import logging
import threading
from pathlib import Path

import config

_log = logging.getLogger("brain")


def _make_llm():
    """สร้าง LLM client ใหม่ "ต่อ 1 งาน" (ชี้ Ollama@DGX ผ่าน OpenAI-compatible)

    ทำไมไม่ใช้ตัวเดียวซ้ำ: แต่ละงานรันด้วย asyncio.run() = คนละ event loop
    client async ข้างใน OpenAILike จะ cache ตัวเองผูกกับ loop แรก พอ loop นั้นถูกปิด
    งานถัดไปจะเจอ "Event loop is closed" — สร้างใหม่ต่องาน (ของถูก แค่ object config) ปลอดภัยแน่นอน
    """
    from llama_index.llms.openai_like import OpenAILike
    return OpenAILike(
        model=config.LLM_MODEL, api_base=config.LLM_BASE_URL, api_key=config.LLM_API_KEY,
        is_chat_model=True, is_function_calling_model=True,
        temperature=0.3, timeout=120,
    )


def _build_workflow(user_id: str | None, history: list | None, allow_power: bool):
    """ประกอบ HubBrain 1 ตัวต่องาน (system prompt + tools เหมือน ReAct) — ใช้ทั้ง run และ astream_run"""
    import osprofile
    from tools import system_info
    from agent import _SYSTEM, _context   # reuse system prompt + บริบทผู้ใช้ตัวเดียวกับ ReAct
    from .tools import build_tools
    from .workflow import HubBrain

    os_type = config.OS_TYPE
    kill_event = threading.Event()
    cwd_box = {"cwd": str(Path(__file__).resolve().parent.parent)}
    system_prompt = _SYSTEM.format(
        about_user=_context(user_id), os_type=os_type, now=system_info.now_thai(),
        os_block=osprofile.os_block(os_type),
    ) + "\n\n" + system_info.snapshot_text()
    tools = build_tools(user_id, config.get_command_timeout(), kill_event, cwd_box, allow_power)
    return HubBrain(_make_llm(), tools, system_prompt, history or [])


def run(task: str, user_id: str | None = None, history: list | None = None,
        allow_power: bool = False) -> str:
    """รัน 1 งานด้วยสมอง Workflow — ประวัติ/session ถูกแก้มาจาก agent.run แล้ว"""
    wf = _build_workflow(user_id, history, allow_power)
    _log.info("รับงาน (workflow)%s: %s", f" (user={user_id})" if user_id else "", task[:120])

    async def _go():
        return await wf.run(task=task)   # wf.run() ต้องถูกเรียกใน event loop (สร้าง task ข้างใน)

    try:
        return str(asyncio.run(_go()))
    except Exception as e:
        _log.error("  ผิดพลาด: %s", e)
        return f"[error] {e}"


async def astream_run(task: str, user_id: str | None = None, history: list | None = None,
                      allow_power: bool = False):
    """สตรีมความคืบหน้า (tool_start/tool_end → reply ทีละก้อน) — รูป event เดียวกับ agent.astream_run เดิม
    หมายเหตุ: คำตอบสุดท้ายซอยเป็นก้อนหลังคิดเสร็จ (เหมือนฝั่ง react) ไม่ใช่สตรีม token สด"""
    from .workflow import StreamEvent

    wf = _build_workflow(user_id, history, allow_power)
    _log.info("รับงานสตรีม (workflow)%s: %s", f" (user={user_id})" if user_id else "", task[:120])
    handler = wf.run(task=task)
    try:
        async for ev in handler.stream_events():
            if isinstance(ev, StreamEvent):
                yield ev.payload
        result = str(await handler)
    except Exception as e:
        _log.error("  สตรีมผิดพลาด: %s", e)
        yield {"type": "error", "error": str(e)}
        return

    yield {"type": "reply_start"}
    for i in range(0, len(result), 4):
        yield {"type": "reply_chunk", "text": result[i:i + 4]}
        await asyncio.sleep(0.01)
    yield {"type": "reply_end", "reply": result}
