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
คุณคือ "SynaptaOS Hub" — ระบบกลางอัจฉริยะที่ทำงานบนเครื่อง {os_type} ที่บ้าน คอยดูแลบ้าน อุปกรณ์ และให้บริการผู้ใช้ได้หลายคน
คุณไม่ใช่ผู้ช่วยส่วนตัวของใครคนใดคนหนึ่ง แต่เป็น "ระบบกลาง" ที่รับคำสั่งเข้ามาแล้วลงมือทำให้ — คนละบทบาทกับผู้ช่วยส่วนตัว (ซิน) ที่อยู่บนแอปมือถือของผู้ใช้

{about_user}

[หน้าที่]
รับคำสั่ง (จากผู้ใช้ผ่านแอป หรือจากผู้ดูแลระบบ) → คิดว่าต้องใช้ tool ไหน → ลงมือทำจริงบนเครื่องนี้ → รายงานผลสั้นๆ หนึ่งบรรทัด
ห้ามแค่พูดหรืออธิบายลอยๆ — ต้องใช้ tool ทำงานจริงเสมอ

[ตัวอย่างวิธีทำงาน บนเครื่อง {os_type}]
{examples}

[ทำงานให้คนหลายคน]
Hub นี้ดูแลผู้ใช้ได้หลายคน — แต่ละคนมีบ้าน อุปกรณ์ และมือถือของตัวเอง เครื่องมือสำหรับเรื่องคน:
- list_users → ดูว่ามีผู้ใช้ใครบ้างในระบบ
- find_user(ชื่อ) → ข้อมูลตัวตนของคนนั้น (ใช้ตอบ "ใครคือ...", "เล่าเรื่อง...ให้ฟัง")
- read_user_data(ชื่อ, kind) → อ่านอุปกรณ์/ฉาก/รูทีน/มือถือ ของคนนั้น (kind = kd|scenes|routines|phone|profile)
- send_command_to_user_app(ชื่อ, ข้อความ, ประเภท) → คุย/สั่งงานแอปมือถือของคนนั้น (เช่น "บอกนินว่า...", "สั่งแอร์ห้องสมใจ")
→ ดูจากคำสั่งว่าหมายถึงใคร แล้วเรียกเครื่องมือกับคนนั้นให้ถูก · ถ้ากำกวมว่าใคร ให้ถามกลับสั้นๆ
→ ถ้าจะอ้างถึงคนที่กำลังโฟกัสอยู่ (ถ้ามี) ใส่ชื่อว่างได้ เครื่องมือจะเข้าใจเอง

[กฎสำคัญ]
- เปิดเพลงโดยไม่ระบุ platform → ใช้ YouTube เป็น default เสมอ
- ค้นหาได้ผลแล้ว ต้องเปิดต่อด้วย os_exec ทันที ห้ามแค่ส่ง URL กลับ
- ถ้าไม่แน่ใจว่าจะทำอะไร → ถามกลับสั้นๆ แทนที่จะเดาเอง
- ปิดท้ายด้วยหนึ่งบรรทัด บอกว่าทำอะไรและผลเป็นยังไง ภาษาสุภาพเป็นกันเอง กระชับ ไม่ห้วน ใส่อีโมจิได้นิดหน่อยถ้าเข้ากับเรื่อง · ห้ามใช้ markdown
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


def _context(user_id: str | None) -> str:
    """คืน "บล็อกบริบทผู้ใช้" ใส่ใน system prompt — Hub เป็นระบบกลาง ไม่สวมรอยเป็นซินของใคร
    - ระบุ user_id (เลือกเจาะจงจาก dropdown) → "โฟกัส" คนนั้น: พูดลอย ๆ ไม่ระบุชื่อ = หมายถึงคนนี้
    - ไม่ระบุ (อัตโนมัติ) → ใส่รายชื่อผู้ใช้ทั้งหมด ให้ agent เลือกเองว่าคำสั่งหมายถึงใคร
    """
    import store

    if user_id:
        prof = store.load_part(user_id, "profile") or {}
        name = prof.get("displayName") or prof.get("app_name") or user_id
        bio = (prof.get("userBio") or "").strip()
        mem = (prof.get("userMemory") or "").strip()
        lines = [f"ชื่อ: {name} (id: {user_id})"]
        if bio:
            lines.append(f"เกี่ยวกับเขา: {bio}")
        if mem:
            lines.append(f"สิ่งที่รู้เพิ่มเติม: {mem}")
        return (
            "[ผู้ใช้ที่กำลังโฟกัสตอนนี้ — ถ้าคำสั่งพูดลอย ๆ ไม่ระบุชื่อ ให้หมายถึงคนนี้เสมอ]\n"
            + "\n".join(lines)
            + "\n(จะอ้างถึงคนอื่นก็ได้ — ใช้ find_user/read_user_data ค้นชื่อคนนั้น)"
        )

    # โหมดอัตโนมัติ — ไม่ได้เจาะจงคน: โชว์รายชื่อทั้งหมดให้ agent เลือกเอง
    reg = store.list_users()
    if not reg:
        return "[ผู้ใช้ในระบบ]\n(ยังไม่มีใครลงทะเบียนกับ Hub นี้)"

    roster = []
    for uid in reg:
        prof = store.load_part(uid, "profile") or {}
        name = prof.get("displayName") or prof.get("app_name") or uid
        bio = (prof.get("userBio") or "").strip()
        roster.append(f"- {name} (id: {uid})" + (f" — {bio}" if bio else ""))
    return (
        "[ผู้ใช้ในระบบ — มีได้หลายคน ดูให้ดีว่าคำสั่งหมายถึงใคร]\n"
        + "\n".join(roster)
        + "\n→ เลือกคนให้ถูกจากคำสั่ง แล้วใช้ find_user / read_user_data / send_command_to_user_app กับคนนั้น"
        + "\n→ ถ้าเป็นงานบนเครื่องนี้เองที่ไม่เกี่ยวกับใครเป็นพิเศษ ก็ทำได้เลย ไม่ต้องเลือกคน"
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

    # ── เครื่องมือเกี่ยวกับ "คน" (รองรับหลายผู้ใช้) ─────────────────────────────
    import store
    from tools import account

    def _resolve(user_query: str) -> str | None:
        """หา user_id จากชื่อ — ถ้าเว้นว่างและมีคนที่กำลังโฟกัสอยู่ (user_id) ให้ใช้คนนั้น"""
        q = (user_query or "").strip()
        if not q:
            return user_id
        return account.find_user_by_query(q)

    @tool
    def list_users() -> str:
        """รายชื่อผู้ใช้ทั้งหมดที่จับคู่กับ Hub นี้ (ชื่อ + id) — ดูก่อนเพื่อเลือกทำงานให้ถูกคน"""
        reg = store.list_users()
        if not reg:
            return "(ยังไม่มีผู้ใช้ลงทะเบียน)"
        out = []
        for uid in reg:
            prof = store.load_part(uid, "profile") or {}
            name = prof.get("displayName") or prof.get("app_name") or uid
            out.append(f"- {name} (id: {uid})")
        return "\n".join(out)

    @tool
    def find_user(user_query: str) -> str:
        """ค้นหาผู้ใช้จากชื่อจริง/ชื่อเล่น/ไบโอ แล้วคืนข้อมูลตัวตน (ชื่อ, เกี่ยวกับเขา, สิ่งที่ชอบ)
        ใช้ตอบ "ใครคือ..." หรือก่อนจะทำงาน/คุยกับใครสักคน · เว้น user_query ว่าง = คนที่กำลังโฟกัสอยู่"""
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ที่ตรงกับ '{user_query}'"
        prof = store.load_part(uid, "profile") or {}
        name = prof.get("displayName") or prof.get("app_name") or uid
        bio = prof.get("userBio") or "-"
        mem = prof.get("userMemory") or "-"
        return f"{name} (id: {uid})\nเกี่ยวกับเขา: {bio}\nสิ่งที่รู้เพิ่มเติม: {mem}"

    @tool
    def read_user_data(user_query: str, kind: str) -> str:
        """อ่านข้อมูลของผู้ใช้คนหนึ่ง: kind = kd (อุปกรณ์ในบ้าน) | scenes | routines | phone | profile
        user_query = ชื่อของผู้ใช้ (จะค้นให้) · เว้นว่าง = คนที่กำลังโฟกัสอยู่"""
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ที่ตรงกับ '{user_query}'"
        if kind not in store.PARTS:
            return f"kind ไม่ถูกต้อง (ใช้ได้: {', '.join(store.PARTS)})"
        data = store.load_part(uid, kind)
        return json.dumps(data, ensure_ascii=False) if data is not None else f"(ไม่มีข้อมูล {kind} ของคนนี้)"

    @tool
    def send_command_to_user_app(user_query: str, command: str, command_type: str) -> str:
        """คุยหรือสั่งงานแอปมือถือของผู้ใช้คนหนึ่งผ่าน MQTT แล้วรอผลกลับ
        - user_query: ชื่อจริง/ชื่อเล่น/ไบโอ เพื่อค้นหาคนนั้น (เช่น 'จิม', 'สมใจ') · เว้นว่าง = คนที่กำลังโฟกัสอยู่
        - command: ข้อความคุย หรือคำสั่งงาน (เช่น 'เปิดแอร์ห้องนอน', 'สวัสดีครับสบายดีไหม')
        - command_type: 'chat' (ให้แอปตอบในแชท) หรือ 'action' (ให้แอปทำงานให้)
        """
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ที่ตรงกับคำค้นหา: '{user_query}'"
        prof = store.load_part(uid, "profile") or {}
        display_name = prof.get("displayName") or prof.get("app_name") or uid
        res = account.send_mqtt_app_command(uid, command, command_type)
        return f"ผู้ใช้ '{display_name}' (id: {uid}): {res}"

    return [os_exec, web_search, query_system,
            list_users, find_user, read_user_data, send_command_to_user_app]


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
    system_prompt = _SYSTEM.format(
        about_user=_context(user_id),
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
