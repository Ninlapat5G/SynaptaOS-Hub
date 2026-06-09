"""
tools — เครื่องมือของสมอง (LlamaIndex FunctionTool) — ตรงกับชุดของ agent.py เดิม

ตัวฟังก์ชันเรียกเข้าโมดูลเดียวกับฝั่ง ReAct (os_exec/web_search/account/store/device_state/iot)
ต่างกันแค่ "เปลือก" ที่ห่อให้ LlamaIndex รู้จัก → สลับสมองได้โดยพฤติกรรมเครื่องมือเหมือนเดิม
"""
import json
import threading
from typing import Literal

from llama_index.core.tools import FunctionTool

import config


def build_tools(user_id: str | None, timeout: float, kill_event: threading.Event,
                cwd_box: dict, allow_power: bool) -> list[FunctionTool]:
    import store
    from tools import account, os_exec as _os_exec, web_search as _web_search, system_info

    def _resolve(user_query: str) -> str | None:
        q = (user_query or "").strip()
        return account.find_user_by_query(q) if q else user_id

    def system_exec(command: str) -> str:
        """รันคำสั่ง terminal บนเครื่อง Hub นี้ (รองรับ cd — โฟลเดอร์ค้างข้ามคำสั่งภายใน task เดียว)"""
        return _os_exec.run(command, timeout=timeout, kill_event=kill_event,
                            cwd_box=cwd_box, allow_power=allow_power)

    def web_search(query: str) -> str:
        """ค้นข้อมูลบนเว็บที่จำเป็นต่อการทำงาน (ลิงก์จริง/ข่าว/อากาศ/ราคา ฯลฯ)"""
        return _web_search.search(query)

    def system_status() -> str:
        """ดูสถานะเครื่อง Hub: OS, การใช้ดิสก์และหน่วยความจำ"""
        return system_info.snapshot_text()

    def user_list() -> str:
        """รายชื่อผู้ใช้ทั้งหมดที่จับคู่กับ Hub นี้ (ชื่อ + id)"""
        reg = store.list_users()
        if not reg:
            return "(ยังไม่มีผู้ใช้ลงทะเบียน)"
        return "\n".join(f"- {(store.load_part(u, 'profile') or {}).get('displayName') or u} (id: {u})" for u in reg)

    def user_find(user_query: str = "") -> str:
        """ค้นหาผู้ใช้จากชื่อ/ไบโอ คืนข้อมูลตัวตน · เว้นว่าง = คนที่กำลังโฟกัสอยู่"""
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ '{user_query}'"
        prof = store.load_part(uid, "profile") or {}
        name = prof.get("displayName") or prof.get("app_name") or uid
        return f"{name} (id: {uid})\nเกี่ยวกับเขา: {prof.get('userBio') or '-'}\nเพิ่มเติม: {prof.get('userMemory') or '-'}"

    def user_remember(note: str, user_query: str = "") -> str:
        """จำสิ่งสำคัญเกี่ยวกับผู้ใช้ไว้ใช้ครั้งหน้า · เว้น user_query = คนที่กำลังโฟกัสอยู่"""
        uid = _resolve(user_query)
        note = (note or "").strip()
        if not uid or not note:
            return "ไม่มีอะไรให้จำ หรือไม่รู้ว่าจะจำให้ใคร"
        prof = store.load_part(uid, "profile") or {}
        mem = (prof.get("hubMemory") or "").strip()
        if note in mem:
            return "จำเรื่องนี้ไว้อยู่แล้วค่ะ"
        lines = [l for l in mem.split("\n") if l.strip()] + [f"- {note}"]
        store.save_part(uid, "profile", {"hubMemory": "\n".join(lines[-30:])})
        return "จำไว้ให้แล้วค่ะ ✨"

    def user_read_data(kind: Literal["kd", "scenes", "routines", "phone", "profile"],
                       user_query: str = "") -> str:
        """อ่านข้อมูลผู้ใช้: kd(อุปกรณ์)/scenes/routines/phone/profile · เว้น user_query = คนที่โฟกัสอยู่"""
        import device_state
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ '{user_query}'"
        data = store.load_part(uid, kind)
        if kind == "kd" and isinstance(data, list):
            slim = []
            for d in data:
                item = {k: d[k] for k in ("name", "room", "topic", "type", "unit") if d.get(k)}
                st = device_state.get(d.get("topic", ""))
                if st is not None:
                    item["state"] = st
                slim.append(item)
            return json.dumps(slim, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False) if data is not None else f"(ไม่มีข้อมูล {kind})"

    def user_send_command(command: str, command_type: Literal["chat", "action"],
                          user_query: str = "") -> str:
        """ส่งข้อความ/คำสั่งแบบ Agent-to-Agent ไปยังผู้ช่วยบนมือถือของผู้ใช้ · เว้น user_query = คนที่โฟกัสอยู่"""
        uid = _resolve(user_query)
        if not uid:
            return f"ไม่พบผู้ใช้ '{user_query}'"
        return account.send_app_command(uid, command, command_type, sender=config.AGENT_NAME)

    def iot_set(topic: str, value: str) -> str:
        """ควบคุมอุปกรณ์ IoT ผ่าน MQTT — value: 'true'/'false' (digital) หรือเลข 0-255 (analog)"""
        from tools.iot import publish_set
        return publish_set(topic, value)

    def iot_get_state(topic: str) -> str:
        """อ่านสถานะล่าสุดของอุปกรณ์ IoT ตาม topic"""
        import device_state
        val = device_state.get(topic)
        return f"{topic} = {val}" if val is not None else f"ไม่พบสถานะของ {topic}"

    fns = [system_exec, web_search, system_status, user_list, user_find, user_remember,
           user_read_data, user_send_command, iot_set, iot_get_state]
    return [FunctionTool.from_defaults(fn=f, name=f.__name__) for f in fns]
