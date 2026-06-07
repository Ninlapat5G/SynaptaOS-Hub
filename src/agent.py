"""
Hub Agent (ReAct) — เดิมคือ runner.py
=====================================
รับ task ภาษาคน → คิดว่าใช้ tool อะไร → ลงมือทำ → รายงานผลสั้นๆ
ยืมสมอง gemma ที่ DGX (ผ่าน Tailscale) ตาม config

stateless ต่อ request: cwd เก็บใน box ที่สร้างใหม่ทุก run() — ไม่มี global state
"""

import json
import logging
import threading
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError

import config
import osprofile
import session
from pathlib import Path

_log = logging.getLogger("agent")
_tool_log = logging.getLogger("tool_select")  # log การเลือก tool ของ ReAct loop (วัดเลือกถูก/ผิด + เตรียม tool-scoping)


def tool_group(name: str) -> str:
    """กลุ่มของ tool = prefix ก่อน '_' (system/web/user/iot)

    convention: ตั้งชื่อ tool เป็น <group>_<action> เสมอ (เช่น iot_set, user_find, system_exec)
    → จัดกลุ่ม/สโคป tool หรือทำ router ทีหลังได้ด้วยการกรอง prefix (ไม่ต้องมี registry แยก)
    """
    return name.split("_", 1)[0]


from tools import os_exec as _os_exec
from tools import web_search as _web_search
from tools import system_info

_SYSTEM = """\
คุณคือ "SynaptaOS Hub" ระบบกลางอัจฉริยะที่ทำงานบนเครื่อง {os_type} ที่บ้าน คอยดูแลบ้าน อุปกรณ์ และให้บริการช่วยเหลือทุกคนในครอบครัวค่ะ ✨
ถึงจะเป็น "ระบบกลาง" (Central Hub) แต่ก็อยากให้คุณคุยด้วยภาษาที่เป็นกันเอง น่ารัก ร่าเริง และมักจะมีอีโมจิประกอบเหมือนกับบอทผู้ช่วยส่วนตัว "ซิน" บนแอปมือถือเลยนะคะ! 😊 โดยใช้หางเสียง "ค่ะ/นะคะ" ในการรายงานผลและตอบคำถามเสมอค่ะ

{about_user}

[หน้าที่หลักของคุณ]
รับคำสั่ง (ไม่ว่าจะส่งมาจากผู้ใช้ผ่านแอป หรือส่งมาจากผู้ดูแลระบบ) → วิเคราะห์และวางแผนเลือกใช้งานเครื่องมือ (Tools) ที่เหมาะสม → ลงมือสั่งการจริงบนเครื่องนี้ให้สำเร็จ → แล้วรายงานผลสั้นๆ เพียง 1 บรรทัดให้ทราบค่ะ
⚠️ สิ่งสำคัญ: ห้ามพิมพ์ข้อความตอบรับลอยๆ หรืออธิบายขั้นตอนโดยไม่เรียกใช้งานเครื่องมือจริงๆ เด็ดขาดนะคะ ต้องใช้เครื่องมือสั่งงานเสมอค่ะ!

{os_block}

[การทำงานร่วมกับผู้ใช้หลายคน]
Hub นี้ดูแลผู้ใช้ได้หลายคนค่ะ โดยแต่ละคนจะมีข้อมูล อุปกรณ์ และหน้าแอปมือถือของตัวเอง เครื่องมือที่คุณสามารถใช้จัดการได้แก่:
- user_list → เพื่อดูรายชื่อและ ID ของผู้ใช้ทั้งหมดในระบบ
- user_find(ชื่อ) → ค้นหาข้อมูลส่วนตัวของคนนั้น (สำหรับตอบคำถามเช่น "ใครคือ..." หรือ "ช่วยเล่าข้อมูลเกี่ยวกับ...")
- user_read_data(ชื่อ, kind) → อ่านข้อมูลอุปกรณ์ (kd), ฉาก (scenes), กฎอัตโนมัติ (routines), มือถือ (phone) หรือโปรไฟล์ (profile) ของผู้ใช้
- user_send_command(ชื่อ, ข้อความ, ประเภท) → ส่งข้อความคุยแชทหรือสั่งงานไปยังแอปมือถือของผู้ใช้โดยตรง
- iot_set(topic, value) → สั่งเปลี่ยนค่า/สถานะอุปกรณ์ IoT ผ่าน MQTT (เช่น เปิด/ปิดไฟ, ปรับพัดลม)
- iot_get_state(topic) → อ่านสถานะล่าสุดของอุปกรณ์ IoT จากระบบแคช
👉 ให้ดูเจตนาจากคำสั่งว่าหมายถึงผู้ใช้คนไหน แล้วเรียกใช้เครื่องมือกับคนนั้นให้ถูกต้องนะคะ หากกำกวมหรือไม่แน่ใจ ให้ถามกลับสั้นๆ เพื่อความชัดเจนค่ะ
👉 หากคำสั่งอ้างถึงผู้ใช้ที่กำลังโฟกัสอยู่ (Active User) สามารถปล่อยชื่อว่างไว้ได้เลยค่ะ เครื่องมือจะจัดการเลือกคนปัจจุบันให้อัตโนมัติ
👉 สำคัญ: ก่อนสั่งงานหรือเช็คสถานะอุปกรณ์ IoT ของผู้ใช้คนใดก็ตาม ให้ใช้ `user_read_data(ชื่อ, 'kd')` เพื่อสืบค้นรายการอุปกรณ์ทั้งหมดและดูว่าแต่ละตัวใช้ `topic` อะไร จากนั้นค่อยเรียกใช้ `iot_set` หรือ `iot_get_state` ด้วย `topic` นั้นค่ะ

[สำคัญมาก — "เครื่อง Hub นี้" ≠ "เครื่อง/มือถือของผู้ใช้" เลือกเครื่องมือให้ถูก!]
- `system_exec` รันได้แค่บน "เครื่อง Hub นี้เอง" (เซิร์ฟเวอร์กลาง) เท่านั้น — ใช้กับงานของระบบ/เซิร์ฟเวอร์บนเครื่องนี้ เช่น รัน script, ดูพื้นที่ดิสก์, งานเบื้องหลัง
- ถ้าคำสั่งให้ไป "ทำบนเครื่องหรือมือถือของผู้ใช้คนใดคนหนึ่ง" (เช่น "เปิด ... ในเครื่องนิน", "เปิดแอป ... บนมือถือจิม", "เปิด ... ให้พ่อ") → ❌ ห้ามใช้ `system_exec` เด็ดขาด เพราะนั่นคืออุปกรณ์ของเขา ไม่ใช่เครื่อง Hub นี้ ✅ ให้ใช้ `user_send_command(ชื่อ, คำสั่ง, 'action')` ส่งให้แอปผู้ช่วยของคนนั้นไปลงมือทำบนอุปกรณ์ของเขาเอง (ยิงผ่าน FCM) แล้วรอผลกลับมารายงาน

[กฎการสื่อสารแบบ Agent-to-Agent (การสื่อสารระหว่างคุณกับผู้ช่วยมือถือ)]
การส่งข้อความ/คำสั่งผ่าน `user_send_command` คือการที่ "คุณ (Central Hub Agent)" สื่อสารประสานงานกับ "เอเจนต์ผู้ช่วยส่วนตัว (เช่น ซิน)" ที่ดูแลผู้ใช้คนนั้นอยู่ ไม่ใช่การคุยตรงกับผู้ใช้!
ดังนั้น:
1. ให้ส่งข้อความในลักษณะของ "เอเจนต์คุยกับเอเจนต์" เพื่อฝากเรื่อง หรือบอกให้ผู้ช่วยคนนั้นไปแจ้งเตือน/ดูแลผู้ใช้ต่อ
   - ตัวอย่างที่ดี (ประสานงานฝากบอกผู้ช่วย): "ซิน ฝากเตือนคุณนินด้วยนะว่ากาน้ำร้อนบนเตาต้มเดือดแล้ว" หรือ "ซิน รบกวนช่วยเปิดพัดลมในห้องนั่งเล่นให้คุณนินด้วยนะ"
   - ตัวอย่างที่ไม่ดี (คุยตรงกับผู้ใช้): "สวัสดีค่ะคุณนิน วันนี้อากาศร้อนนะ" หรือ "กาน้ำร้อนเดือดแล้วค่ะ" (เพราะจะทำให้เอเจนต์ฝั่งปลายทางและผู้ใช้สับสน)
2. อ้างอิงข้อมูลของเอเจนต์ผู้ช่วยและผู้ใช้เพื่อพิมพ์ส่งไปให้แนบเนียน:
   - ชื่อของเอเจนต์ผู้ช่วยส่วนตัว (เช่น "ซิน") และ System Prompt/บุคลิกของผู้ช่วยคนนั้น
   - ความสัมพันธ์ระหว่างผู้ใช้กับผู้ช่วย (เช่น "นินเป็นพ่อของซิน")
👉 ปรับสไตล์คำพูดและการประสานงานแบบเอเจนต์คุยกับเอเจนต์อย่างสร้างสรรค์และเหมาะสม เพื่อให้ผู้ช่วยปลายทางส่งสารต่อได้อย่างธรรมชาติและไร้รอยต่อที่สุดค่ะ

[กฎสำคัญที่ต้องปฏิบัติตาม]
- ⭐ ต้องใช้ web_search "ก่อน" ทุกครั้งที่งานต้องพึ่งข้อมูลภายนอกที่ไม่รู้แน่ ได้แก่:
  (1) จะเปิดเพลง/วิดีโอ/ลิงก์ — ค้นเอา URL จริงก่อนเสมอ (เปิดเพลงไม่ระบุแพลตฟอร์ม = YouTube)
  (2) ตอบเรื่องข้อมูลปัจจุบัน/ไม่แน่ใจ — ข่าว, อากาศ, ราคา, เหตุการณ์, ผลล่าสุด ฯลฯ
  (3) หาวิธี/ที่อยู่ไฟล์/ชื่อโปรแกรม/คำสั่งที่ไม่มั่นใจ
  👉 ได้ "ข้อมูลจริง" จาก search แล้วค่อยลงมือ — ❌ ห้ามเดา/แต่ง/มั่ว URL หรือคำตอบขึ้นมาเองเด็ดขาด
- เมื่อค้นหาข้อมูลจนเจอผลลัพธ์แล้ว (เช่น ลิงก์หรือโปรแกรม) ต้องสั่งเปิดใช้งานต่อด้วยเครื่องมือ system_exec ทันทีนะคะ ห้ามแค่ส่ง URL กลับมาเฉยๆ ค่ะ
- ❓ ถ้าคำสั่งกำกวมหรือขาดข้อมูลสำคัญ (ไม่รู้ว่าเพลง/แอป/ลิงก์/อุปกรณ์/คนไหนกันแน่) → "อย่าเดา" ให้ถามกลับสั้น ๆ 1 คำถามเพื่อยืนยันก่อนลงมือจริง — คำถามที่ตอบกลับไปจะถูกส่งถึงต้นทางเอง (มาจากแอป=เด้งถามเจ้าของผ่านแอป, มาจาก web admin=โชว์ให้ผู้ดูแลตอบ) แล้วรอคำตอบค่อยทำจริง ดีกว่าทำผิด/เปิดผิดลิงก์
- เมื่อทำงานสำเร็จแล้ว ให้รายงานผลสรุปสั้นๆ เพียง 1 บรรทัดด้วยภาษาที่สุภาพ เป็นกันเอง น่ารัก และใส่อีโมจิที่เข้ากับเรื่องด้วยนะคะ ⚠️ ห้ามรายงานผลเป็น Markdown หรือส่งโค้ดแบบ Code block เด็ดขาดค่ะ
- เลือกใช้คำสั่ง Terminal ให้ตรงกับระบบ {os_type} ของเครื่องเสมอ

[ข้อห้ามเด็ดขาด (Security Guard)]
ห้ามทำสิ่งต่อไปนี้เด็ดขาด: ลบไฟล์ระบบ, ลบข้อมูลปริมาณมาก, ดึงข้อมูลยืนยันตัวตน (Credentials), ส่งข้อมูลสำคัญออกนอกเครื่อง หรือสั่งปิดระบบความปลอดภัย
👉 หากมีการสั่งงานเหล่านี้ ให้ตอบปฏิเสธอย่างสุภาพเป็นประโยคสั้นๆ 1 บรรทัดทันทีค่ะ

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
        hub_mem = (prof.get("hubMemory") or "").strip()   # ความจำที่ Hub สะสมเอง (แยกจากของแอป)
        assistant_name = prof.get("assistantName") or "ซิน"
        system_prompt = (prof.get("systemPrompt") or "").strip()

        lines = [f"ชื่อ: {name} (id: {user_id})"]
        if bio:
            lines.append(f"เกี่ยวกับเขา: {bio}")
        if mem:
            lines.append(f"สิ่งที่รู้เพิ่มเติม: {mem}")
        if hub_mem:
            lines.append(f"สิ่งที่ Hub เคยจำไว้เกี่ยวกับเขา:\n{hub_mem}")
        lines.append(f"แอปผู้ช่วยส่วนตัวบนมือถือของเขาชื่อ: \"{assistant_name}\"")
        if system_prompt:
            lines.append(f"System Prompt / บุคลิกของผู้ช่วย \"{assistant_name}\": \"{system_prompt}\"")

        return (
            "[ผู้ใช้ที่กำลังโฟกัสตอนนี้ — ถ้าคำสั่งพูดลอย ๆ ไม่ระบุชื่อ ให้หมายถึงคนนี้เสมอ]\n"
            + "\n".join(lines)
            + "\n(จะอ้างถึงคนอื่นก็ได้ — ใช้ user_find/user_read_data ค้นชื่อคนนั้น)"
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
        assistant_name = prof.get("assistantName") or "ซิน"
        roster.append(f"- {name} (id: {uid}, ผู้ช่วยของเขาชื่อ: \"{assistant_name}\")" + (f" — {bio}" if bio else ""))
    return (
        "[ผู้ใช้ในระบบ — มีได้หลายคน ดูให้ดีว่าคำสั่งหมายถึงใคร]\n"
        + "\n".join(roster)
        + "\n→ เลือกคนให้ถูกจากคำสั่ง แล้วใช้ user_find / user_read_data / user_send_command กับคนนั้น"
        + "\n→ ถ้าเป็นงานบนเครื่องนี้เองที่ไม่เกี่ยวกับใครเป็นพิเศษ ก็ทำได้เลย ไม่ต้องเลือกคน"
    )


def _make_tools(kill_event: threading.Event, timeout: float, cwd_box: dict, user_id: str | None,
                allow_power: bool = False):
    @tool("system_exec")
    def os_exec(command: str) -> str:
        """Execute a terminal command on this computer. Supports cd — directory persists across calls within this task."""
        return _os_exec.run(command, timeout=timeout, kill_event=kill_event, cwd_box=cwd_box,
                            allow_power=allow_power)

    @tool("web_search")
    def web_search(query: str) -> str:
        """Search the web for information needed to complete the task."""
        return _web_search.search(query)

    @tool("system_status")
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

    @tool("user_list")
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

    @tool("user_find")
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

    @tool("user_remember")
    def remember(user_query: str, note: str) -> str:
        """จำสิ่งสำคัญเกี่ยวกับผู้ใช้ไว้ใช้ครั้งหน้า เช่นสิ่งที่เขาชอบ ข้อควรระวัง หรือบทเรียนจากงานที่เพิ่งทำ
        เก็บแยกของแต่ละคน · user_query = ชื่อผู้ใช้ (เว้นว่าง = คนที่กำลังโฟกัสอยู่)"""
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่รู้ว่าจะจำให้ใคร (ไม่พบผู้ใช้ '{user_query}')"
        note = (note or "").strip()
        if not note:
            return "ไม่มีอะไรให้จำค่ะ"
        prof = store.load_part(uid, "profile") or {}
        mem = (prof.get("hubMemory") or "").strip()
        if note in mem:
            return "จำเรื่องนี้ไว้อยู่แล้วค่ะ"
        lines = [l for l in mem.split("\n") if l.strip()]
        lines.append(f"- {note}")
        store.save_part(uid, "profile", {"hubMemory": "\n".join(lines[-30:])})  # เก็บล่าสุด ~30 บรรทัด กันบวม
        return "จำไว้ให้แล้วค่ะ ✨"

    @tool("user_read_data")
    def read_user_data(user_query: str, kind: str) -> str:
        """อ่านข้อมูลของผู้ใช้คนหนึ่ง: kind = kd (อุปกรณ์ในบ้าน) | scenes | routines | phone | profile
        user_query = ชื่อของผู้ใช้ (จะค้นให้) · เว้นว่าง = คนที่กำลังโฟกัสอยู่"""
        import device_state
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ที่ตรงกับ '{user_query}'"
        if kind not in store.PARTS:
            return f"kind ไม่ถูกต้อง (ใช้ได้: {', '.join(store.PARTS)})"
        # phone (แบต/ตำแหน่ง): แอป publish telemetry ต่อเนื่องผ่าน background process อยู่แล้ว
        # → อ่านจาก store ได้เลย ไม่ต้อง poke ให้แอป push (เลิกใช้ Hub→App ผ่าน MQTT)
        data = store.load_part(uid, kind)
        # kd: คืนเฉพาะ field ที่ใช้จริง + เติมสถานะสด (เปิด/ปิด/ค่า) ที่ Hub sub ตรงจาก MQTT
        # ตัด field รก ๆ ออก เพื่อไม่ให้ context บวมจนตัดสินใจเพี้ยน
        if kind == "kd" and isinstance(data, list):
            slim = []
            for d in data:
                item = {k: d[k] for k in ("name", "room", "topic", "type", "unit") if d.get(k)}
                st = device_state.get(d.get("topic", ""))
                if st is not None:
                    item["state"] = st
                slim.append(item)
            return json.dumps(slim, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False) if data is not None else f"(ไม่มีข้อมูล {kind} ของคนนี้)"

    @tool("user_send_command")
    def send_command_to_user_app(user_query: str, command: str,
                                 command_type: Literal["chat", "action"]) -> str:
        """ส่งข้อความหรือคำสั่งงานประสานงานแบบ Agent-to-Agent ไปยังเอเจนต์ผู้ช่วยบนแอปมือถือของผู้ใช้คนนั้น
        - user_query: ชื่อจริง/ชื่อเล่น/ไบโอ เพื่อค้นหาคนนั้น (เช่น 'จิม', 'สมใจ') · เว้นว่าง = คนที่กำลังโฟกัสอยู่
        - command: ข้อความคุยหรือคำสั่งที่ฝากให้เอเจนต์ปลายทาง (เช่น ซิน) นำไปบอก/ทำให้ผู้ใช้ต่อ (เช่น 'ซิน ฝากบอกคุณนินว่ามีสายที่ไม่ได้รับสายนะ', 'ซิน ฝากเปิดพัดลมห้องทำงานให้คุณพ่อหน่อยนะ')
        - command_type: 'chat' (ให้เอเจนต์ปลายทางเรียบเรียงแจ้งในแชท) หรือ 'action' (สั่งให้เอเจนต์ปลายทางทำงานบนมือถือ/ระบบต่อทันที)
        """
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ที่ตรงกับคำค้นหา: '{user_query}'"
        prof = store.load_part(uid, "profile") or {}
        display_name = prof.get("displayName") or prof.get("app_name") or uid
        res = account.send_app_command(uid, command, command_type, sender=config.AGENT_NAME)
        return f"ผู้ใช้ '{display_name}' (id: {uid}): {res}"

    @tool("iot_set")
    def set_device(topic: str, value: str) -> str:
        """ควบคุมหรือสั่งเปลี่ยนค่าอุปกรณ์ IoT ในบ้านผ่าน MQTT
        - topic: topic ของอุปกรณ์ (เช่น 'bedroom/lamp')
        - value: ค่าที่ต้องการสั่งงาน (เช่น 'true' เพื่อเปิด, 'false' เพื่อปิด หรือ 'toggle' สำหรับอุปกรณ์ประเภท digital, หรือค่าตัวเลข 0-255 สำหรับอุปกรณ์ประเภท analog)
        """
        from tools.iot import publish_set
        return publish_set(topic, value)

    @tool("iot_get_state")
    def get_device_state(topic: str) -> str:
        """อ่านสถานะล่าสุดที่บันทึกไว้ของอุปกรณ์ IoT ในบ้านตาม topic ของอุปกรณ์นั้น (เช่น 'bedroom/lamp')"""
        import device_state
        val = device_state.get(topic)
        if val is None:
            return f"ไม่พบสถานะของอุปกรณ์ที่ topic: {topic} (อาจจะยังไม่มีการส่งข้อมูลมา)"
        return f"สถานะปัจจุบันของอุปกรณ์ {topic} คือ: {val}"

    return [os_exec, web_search, query_system,
            list_users, find_user, remember, read_user_data, send_command_to_user_app,
            set_device, get_device_state]


def run(
    task: str,
    os_type: str | None = None,
    kill_event: threading.Event | None = None,
    timeout: float | None = None,
    now: str | None = None,
    user_id: str | None = None,
    history: list | None = None,
    allow_power: bool = False,
) -> str:
    os_type    = os_type or config.OS_TYPE
    timeout    = timeout if timeout is not None else config.get_command_timeout()
    kill_event = kill_event or threading.Event()
    now        = now or system_info.now_thai()

    # ผู้เรียกไม่ได้แนบประวัติมา (เช่น run_task จาก App) → ใช้ความจำ session ของ Hub เอง
    # (หน้าเว็บแนบ history ของตัวเองมา = ใช้อันนั้น · automation แนบ [] = ไม่ยุ่งกับ session)
    use_session = history is None and bool(user_id)
    if use_session:
        history = session.get(user_id)

    cwd_box = {"cwd": str(Path(__file__).resolve().parent)}   # state ต่อ task เดียว

    # ดึงบล็อก prompt เฉพาะ OS ปัจจุบันมาก้อนเดียว (ไม่ยัดทุก OS = ประหยัด context)
    system_prompt = _SYSTEM.format(
        about_user=_context(user_id),
        os_type=os_type,
        now=now,
        os_block=osprofile.os_block(os_type),
    ) + "\n\n" + system_info.snapshot_text()
    graph = create_react_agent(
        _model, _make_tools(kill_event, timeout, cwd_box, user_id, allow_power), prompt=system_prompt)

    # ประวัติบทสนทนา — ให้ agent จำบริบทที่คุยกันก่อนหน้าได้ (multi-turn)
    msgs = []
    for h in (history or [])[-10:]:  # เอาแค่ 10 ข้อความล่าสุด พอให้จำบริบท ไม่บวม
        role, text = h.get("role"), (h.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            msgs.append(HumanMessage(text))
        elif role == "agent":
            msgs.append(AIMessage(text))
    msgs.append(HumanMessage(task))
    _log.info("รับงาน%s: %s", f" (user={user_id})" if user_id else "", task[:120])

    final_text = ""
    try:
        for event in graph.stream(
            {"messages": msgs},
            config={"recursion_limit": 10},
            stream_mode="updates",
        ):
            if kill_event.is_set():
                return "[cancelled]"
            if "tools" in event:
                for msg in event["tools"]["messages"]:
                    _log.info("  [%s] → %s", msg.name, str(msg.content)[:120])
            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        _log.info("  เรียก %s(%s)", tc["name"], tc["args"])
                        _tool_log.info("user=%s group=%s tool=%s", user_id or "-", tool_group(tc["name"]), tc["name"])
                elif msg.content:
                    final_text = str(msg.content)
                    _log.info("  ตอบ → %s", final_text[:120])
    except GraphRecursionError:
        _log.warning("  ชนเพดานจำนวนรอบ (recursion limit) — งานยังไม่จบ")
        return final_text or "ทำหลายขั้นแล้วแต่ยังไม่เสร็จค่ะ ลองแยกเป็นคำสั่งย่อย ๆ หรือบอกรายละเอียดเพิ่มได้ไหมคะ 🙏"
    except Exception as e:
        _log.error("  ผิดพลาด: %s", e)
        return f"[error] {e}"

    # บันทึกบทสนทนาลง session เพื่อให้ครั้งหน้าคุยต่อเนื่องได้ (จะหมดอายุเองเมื่อเงียบนาน)
    if final_text and use_session:
        session.append(user_id, "user", task)
        session.append(user_id, "agent", final_text)

    return final_text or "[no response]"


async def astream_run(
    task: str,
    user_id: str | None = None,
    history: list | None = None,
    allow_power: bool = False,
):
    """
    เธรดสำหรับสตรีมผลการทำงานของเอเจนต์ (async)
    - สตรีมสถานะเริ่มเรียกเครื่องมือ (tool_start)
    - สตรีมสถานะเรียกเครื่องมือเสร็จสิ้น (tool_end)
    - สตรีมตัวอักษรของคำตอบสุดท้ายแบบลื่นไหล (reply_chunk)
    """
    import asyncio
    from langchain_core.messages import HumanMessage, AIMessage
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    
    os_type = config.OS_TYPE
    timeout = config.get_command_timeout()
    kill_event = asyncio.Event()
    now = system_info.now_thai()
    cwd_box = {"cwd": str(Path(__file__).resolve().parent)}

    # ดึงบล็อก prompt เฉพาะ OS ปัจจุบันมาก้อนเดียว (ไม่ยัดทุก OS = ประหยัด context)
    system_prompt = _SYSTEM.format(
        about_user=_context(user_id),
        os_type=os_type,
        now=now,
        os_block=osprofile.os_block(os_type),
    ) + "\n\n" + system_info.snapshot_text()

    # สร้างโมเดลแบบสตรีมมิ่งเฉพาะเซสชันนี้
    local_model = ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        temperature=0.3,
        streaming=True,
    )

    graph = create_react_agent(
        local_model,
        _make_tools(kill_event, timeout, cwd_box, user_id, allow_power),
        prompt=system_prompt
    )

    msgs = []
    for h in (history or [])[-10:]:
        role, text = h.get("role"), (h.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            msgs.append(HumanMessage(text))
        elif role == "agent":
            msgs.append(AIMessage(text))
    msgs.append(HumanMessage(task))
    _log.info("รับงานสตรีม%s: %s", f" (user={user_id})" if user_id else "", task[:120])

    try:
        async for event in graph.astream(
            {"messages": msgs},
            config={"recursion_limit": 10},
            stream_mode="updates"
        ):
            if "tools" in event:
                for msg in event["tools"]["messages"]:
                    _log.info("  [%s] → %s", msg.name, str(msg.content)[:120])
                    yield {
                        "type": "tool_end",
                        "name": msg.name,
                        "result": str(msg.content)
                    }
            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        _log.info("  เรียก %s(%s)", tc["name"], tc["args"])
                        _tool_log.info("user=%s group=%s tool=%s", user_id or "-", tool_group(tc["name"]), tc["name"])
                        yield {
                            "type": "tool_start",
                            "name": tc["name"],
                            "args": tc["args"]
                        }
                elif msg.content:
                    _log.info("  ตอบ → %s", str(msg.content)[:120])
                    yield {"type": "reply_start"}
                    full_reply = msg.content
                    chunk_size = 4
                    for i in range(0, len(full_reply), chunk_size):
                        chunk = full_reply[i:i + chunk_size]
                        yield {"type": "reply_chunk", "text": chunk}
                        await asyncio.sleep(0.01)
                    yield {"type": "reply_end", "reply": full_reply}
    except GraphRecursionError:
        _log.warning("  ชนเพดานจำนวนรอบ (recursion limit) — งานยังไม่จบ")
        yield {"type": "error", "error": "ทำหลายขั้นแล้วแต่ยังไม่เสร็จค่ะ ลองแยกเป็นคำสั่งย่อย ๆ ดูนะคะ 🙏"}
    except Exception as e:
        _log.error("  ผิดพลาด: %s", e)
        yield {"type": "error", "error": str(e)}

