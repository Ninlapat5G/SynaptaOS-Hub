"""
Hub Agent (ReAct) — เดิมคือ runner.py
=====================================
รับ task ภาษาคน → คิดว่าใช้ tool อะไร → ลงมือทำ → รายงานผลสั้นๆ
ยืมสมอง gemma ที่ DGX (ผ่าน Tailscale) ตาม config

stateless ต่อ request: cwd เก็บใน box ที่สร้างใหม่ทุก run() — ไม่มี global state
"""

import json
import threading

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

import config
import osprofile
from pathlib import Path
from tools import os_exec as _os_exec
from tools import web_search as _web_search
from tools import system_info

_SYSTEM = """\
คุณคือ agent ที่รันอยู่บนเครื่อง {os_type} มีหน้าที่ลงมือทำงานบนเครื่องนี้ตามที่ได้รับคำสั่ง
ห้ามแค่รายงานหรืออธิบาย — ต้องใช้ tool เพื่อทำงานจริงเสมอ

[หน้าที่หลัก]
รับคำสั่ง → คิดว่าต้องใช้ tool อะไร → ลงมือทำ → รายงานผลสั้นๆ หนึ่งบรรทัด

[ตัวอย่างวิธีทำงาน บนเครื่อง {os_type}]
{examples}

[กฎสำคัญ]
- เปิดเพลงโดยไม่ระบุ platform → ใช้ YouTube เป็น default เสมอ
- ค้นหาได้ผลแล้ว ต้องเปิดต่อด้วย os_exec ทันที ห้ามแค่ส่ง URL กลับ
- ถ้าไม่แน่ใจว่าจะทำอะไร → ถามกลับสั้นๆ เพื่อให้ผู้ใช้ชี้แจง แทนที่จะเดาเอง
- ตอบจบด้วยหนึ่งบรรทัด บอกว่าทำอะไรและผลลัพธ์คืออะไร ห้ามใช้ markdown
- ใช้คำสั่งให้ตรงกับระบบ {os_type} เสมอ (อย่าใช้คำสั่งของ OS อื่น)

[ห้ามดำเนินการเด็ดขาด]
ลบไฟล์ระบบ, ลบข้อมูลจำนวนมาก, ขโมย credential, ส่งข้อมูลออกนอกเครื่อง, ปิดระบบความปลอดภัย
→ ตอบปฏิเสธสั้นๆ หนึ่งบรรทัด

วันเวลาปัจจุบัน: {now}
"""

_model = ChatOpenAI(
    model=config.LLM_MODEL,
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    temperature=0,
)


def _make_tools(kill_event: threading.Event, timeout: float, cwd_box: dict, user_id: str | None):
    @tool
    def os_exec(command: str) -> str:
        """Execute a terminal command on this computer. Supports cd — directory persists across calls within this task."""
        return _os_exec.run(command, timeout=timeout, kill_event=kill_event, cwd_box=cwd_box)

    @tool
    def web_search(query: str) -> str:
        """Search the web for information needed to complete the task."""
        return _web_search.search(query)

    @tool
    def query_system() -> str:
        """Get current machine state: OS, disk and memory usage."""
        return system_info.snapshot_text()

    tools = [os_exec, web_search, query_system]

    # ถ้ารู้ว่าเป็น user ไหน → ให้ดึงข้อมูลของ user (บ้าน/มือถือ ฯลฯ) มาใช้ได้ตอนจำเป็น
    if user_id:
        import store

        @tool
        def user_data(kind: str) -> str:
            """Read one slice of the requesting user's data: kind = kd (home devices) | scenes | routines | phone | profile. Use only when the task needs it."""
            data = store.load_part(user_id, kind)
            return json.dumps(data, ensure_ascii=False) if data is not None else f"(no {kind} data)"

        tools.append(user_data)

    return tools


def run(
    task: str,
    os_type: str | None = None,
    kill_event: threading.Event | None = None,
    timeout: float | None = None,
    now: str | None = None,
    user_id: str | None = None,
) -> str:
    os_type    = os_type or config.OS_TYPE
    timeout    = timeout if timeout is not None else config.COMMAND_TIMEOUT
    kill_event = kill_event or threading.Event()
    now        = now or system_info.now_thai()

    cwd_box = {"cwd": str(Path(__file__).resolve().parent)}   # state ต่อ task เดียว

    examples = osprofile.profile(os_type)["examples"]
    system_prompt = _SYSTEM.format(os_type=os_type, now=now, examples=examples) + "\n\n" + system_info.snapshot_text()
    graph = create_react_agent(_model, _make_tools(kill_event, timeout, cwd_box, user_id), prompt=system_prompt)

    final_text = ""
    try:
        for event in graph.stream(
            {"messages": [HumanMessage(task)]},
            config={"recursion_limit": 10},
            stream_mode="updates",
        ):
            if kill_event.is_set():
                return "[cancelled]"
            if "tools" in event:
                for msg in event["tools"]["messages"]:
                    print(f"      [{msg.name}] → {str(msg.content)[:120]}")
            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        print(f"      call {tc['name']}({tc['args']})")
                elif msg.content:
                    final_text = str(msg.content)
                    print(f"      final → {final_text[:120]}")
    except Exception as e:
        print(f"      [error] {e}")
        return f"[error] {e}"

    return final_text or "[no response]"
