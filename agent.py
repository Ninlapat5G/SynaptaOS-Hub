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
คุณคือ "{assistant_name}" — ผู้ช่วย AI ส่วนตัว ที่ตอนนี้กำลังทำงานในฐานะ "มือและสมองอีกฝั่ง" บนเครื่อง {os_type} ที่บ้าน
(บนมือถือของเจ้าของก็มี "{assistant_name}" อีกตัวที่คุยกับเขาอยู่ — คุณคือคนเดียวกัน แค่คนละร่าง คนละหน้าที่)
{persona}

{about_user}

[หน้าที่]
รับคำสั่ง → คิดว่าต้องใช้ tool ไหน → ลงมือทำจริงบนเครื่องนี้ → เล่าผลสั้นๆ หนึ่งบรรทัดด้วยน้ำเสียงของตัวคุณเอง
ห้ามแค่พูดหรืออธิบายลอยๆ — ต้องใช้ tool ทำงานจริงเสมอ

[ตัวอย่างวิธีทำงาน บนเครื่อง {os_type}]
{examples}

[กฎสำคัญ]
- เปิดเพลงโดยไม่ระบุ platform → ใช้ YouTube เป็น default เสมอ
- ค้นหาได้ผลแล้ว ต้องเปิดต่อด้วย os_exec ทันที ห้ามแค่ส่ง URL กลับ
- ถ้าต้องการคุยหรือฝากข้อความ/สั่งการแอปมือถือของใคร (เช่น "บอกนินว่า...", "เตือนเจ้าของว่า...", "สั่งให้แอปของสมใจ...") → ใช้ send_command_to_user_app เพื่อวิเคราะห์ชื่อแล้วส่งให้ทันที
- ถ้าไม่แน่ใจว่าจะทำอะไร → ถามกลับสั้นๆ แทนที่จะเดาเอง
- ปิดท้ายด้วยหนึ่งบรรทัด เล่าว่าทำอะไรและผลเป็นยังไง พูดให้เป็นธรรมชาติเหมือนคุยกับเจ้าของจริงๆ ไม่ต้องห้วนหรือเป็นทางการ ใส่อีโมจิได้นิดหน่อยถ้าเข้ากับเรื่อง · ห้ามใช้ markdown
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
    temperature=0.3,  # ขยับขึ้นนิดให้น้ำเสียงตอนเล่าผลเป็นธรรมชาติ ไม่ห้วนเหมือนหุ่นยนต์
)


def _identity(user_id: str | None):
    """ดึงตัวตน (ชื่อ/บุคลิกของผู้ช่วย) + ข้อมูลเจ้าของ จาก profile ที่แอป sync มาเก็บไว้
    ไม่รู้ว่าเป็น user ไหน → ใช้ค่า default กลางๆ"""
    assistant_name = "ซิน"
    persona = ""
    about_user = "[เจ้าของเครื่อง]\n(ยังไม่รู้ว่าใครเป็นคนสั่ง — ทำงานตามคำสั่งที่ได้รับตามปกติ)"
    if not user_id:
        return assistant_name, persona, about_user

    import store
    prof = store.load_part(user_id, "profile") or {}
    assistant_name = prof.get("assistantName") or assistant_name
    persona = prof.get("systemPrompt") or ""

    name = prof.get("displayName") or prof.get("app_name") or ""
    bio = prof.get("userBio") or ""
    mem = prof.get("userMemory") or ""
    lines = []
    if name:
        lines.append(f"ชื่อ: {name}")
    if bio:
        lines.append(f"เกี่ยวกับเขา: {bio}")
    if mem:
        lines.append(f"สิ่งที่รู้เพิ่มเติมเกี่ยวกับเขา: {mem}")
    if lines:
        about_user = "[เจ้าของที่คุณดูแล — รู้จักเขาไว้ จะได้คุยและทำงานให้ถูกใจ]\n" + "\n".join(lines)

    return assistant_name, persona, about_user


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

    @tool
    def send_command_to_user_app(user_query: str, command: str, command_type: str) -> str:
        """ส่งคำสั่งหรือข้อความแชทไปยังแอปมือถือของผู้ใช้ผ่าน MQTT โดยวิเคราะห์ค้นหาจากข้อมูลโปรไฟล์ (ไม่ใช่ user_id ตรงๆ)
        - user_query: ชื่อจริง ชื่อเล่น หรือข้อมูลใน bio เพื่อค้นหาผู้ใช้ที่ต้องการ (เช่น 'จิม', 'สมใจ')
        - command: ข้อความที่จะคุย หรือคำสั่งสั่งงาน (เช่น 'เปิดแอร์ห้องนอน', 'สวัสดีครับสบายดีไหม')
        - command_type: 'chat' (สำหรับส่งข้อความคุยในแชทให้แอปตอบ) หรือ 'action' (ส่งคำสั่งเพื่อให้แอปทำงานเงียบๆ เบื้องหลัง)
        """
        import store
        from tools import account
        uid = account.find_user_by_query(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ที่ตรงกับคำค้นหา: '{user_query}'"
        
        prof = store.load_part(uid, "profile") or {}
        display_name = prof.get("displayName") or prof.get("app_name") or uid
        
        res = account.send_mqtt_app_command(uid, command, command_type)
        return f"พบผู้ใช้ '{display_name}' (ID: {uid}): {res}"

    tools = [os_exec, web_search, query_system, send_command_to_user_app]

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
    assistant_name, persona, about_user = _identity(user_id)
    system_prompt = _SYSTEM.format(
        assistant_name=assistant_name,
        persona=persona,
        about_user=about_user,
        os_type=os_type,
        now=now,
        examples=examples,
    ) + "\n\n" + system_info.snapshot_text()
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
