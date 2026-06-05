"""
account — ลงทะเบียนแอป + ซิงก์ข้อมูลผู้ใช้ (รองรับ multi-user)

- register: แอปจับคู่ครั้งแรก (รหัสผ่านด่าน token guard มาแล้ว) → Hub จดแอปไว้
- sync_data: แอปส่งข้อมูล (kd/scenes/routines/phone/profile) มาเก็บ — ส่งเฉพาะตอนเปลี่ยน
- get_user_data: อ่านข้อมูล 1 ส่วนของ user (ให้ agent หยิบเฉพาะที่ต้องใช้ ไม่เปลือง context)

ทุก tool รับ user_id เพราะ MCP over HTTP เป็น stateless — แอปแนบ id ของตัวเองมาทุกครั้ง
"""

import json
import logging

import config
import store

_log = logging.getLogger("account")


def register(mcp):
    @mcp.tool()
    def register(user_id: str, app_name: str) -> str:
        """ลงทะเบียนแอปกับ Hub (จับคู่ครั้งแรก). user_id = รหัสประจำแอป, app_name = ชื่อที่โชว์. Hub จะจดไว้เพื่อให้สั่งงานและเก็บข้อมูลแยกตามผู้ใช้
        คืน telemetry_topic = topic MQTT ที่แอปต้อง publish สถานะมือถือ (แบต/ตำแหน่ง) ขึ้นมาให้ Hub"""
        r = store.register_user(user_id, app_name)
        return json.dumps({"ok": True, "telemetry_topic": f"users/{user_id}/telemetry", **r}, ensure_ascii=False)

    @mcp.tool()
    def sync_data(user_id: str, kind: str, data_json: str) -> str:
        """ส่งข้อมูลของผู้ใช้มาเก็บที่ Hub. kind = kd|scenes|routines|phone|profile, data_json = ข้อมูลในรูป JSON string. ส่งเฉพาะตอนข้อมูลเปลี่ยน"""
        if not store.is_registered(user_id):
            return json.dumps({"ok": False, "error": "ยังไม่ได้ลงทะเบียน — register ก่อน"}, ensure_ascii=False)
        try:
            data = json.loads(data_json)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"data_json ไม่ใช่ JSON: {e}"}, ensure_ascii=False)
        try:
            store.save_part(user_id, kind, data)
        except ValueError as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        return json.dumps({"ok": True, "kind": kind}, ensure_ascii=False)


# ── ฟังก์ชันอำนวยความสะดวกภายนอก MCP ─────────────────────────────────────────
def find_user_by_query(user_query: str) -> str | None:
    """ค้นหา user_id จาก user_query (เช่น ชื่อเล่น, displayName, หรือ bio)"""
    user_query = user_query.strip().lower()
    if not user_query:
        return None
        
    users = store.list_users()
    best_match = None
    best_score = 0
    
    for uid in users:
        prof = store.load_part(uid, "profile") or {}
        display_name = (prof.get("displayName") or "").strip().lower()
        user_bio = (prof.get("userBio") or "").strip().lower()
        app_name = (prof.get("app_name") or "").strip().lower()
        
        # แมตช์ชื่อตรงๆ
        if user_query == display_name:
            return uid
            
        score = 0
        if user_query in display_name:
            score += 10
        if user_query in app_name:
            score += 5
        if user_query in user_bio:
            score += 2
            
        if score > best_score:
            best_score = score
            best_match = uid
            
    return best_match


def send_app_command(user_id: str, command: str, command_type: str, sender: str | None = None) -> str:
    """ส่งคำสั่ง/ข้อความไปแอปมือถือผ่าน **FCM อย่างเดียว** (ช่องเดียวพอ)

    ทำไมไม่ใช้ MQTT: Hub→App ถ้าจะส่งถึงต้องให้แอปออนไลน์ MQTT ซึ่ง = แอปเปิดอยู่
    แต่ FCM ปลุกได้ทุกสถานะ (เปิด/พับ/ถูกฆ่า) → FCM ส่งถึงครอบคลุมกว่าและไม่ต้องรอ timeout
    (App→Hub ฝั่ง request ยิง MCP ตรงผ่าน Tailscale อยู่แล้ว · MQTT เหลือไว้แค่รับ telemetry จากแอป)
    """
    import time
    import uuid
    from tools import fcm_push

    if sender is None:
        sender = config.AGENT_NAME

    corr_id = f"hub-cmd-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    title = "ซินมีข้อความถึงคุณ" if command_type == "chat" else "Hub ฝากงานให้ทำ"
    body = command if len(command) <= 120 else command[:117] + "..."
    sent = fcm_push.send(user_id, title, body, {
        "corr_id": corr_id,
        "sender": sender,
        "type": command_type,
        ("text" if command_type == "chat" else "action_prompt"): command,
    })
    if sent:
        _log.info("ส่ง FCM (%s) ให้ %s: %s", command_type, user_id, command[:80])
        return f"ส่งให้แอปผ่าน FCM แล้ว (corr_id: {corr_id})"
    _log.warning("ส่ง FCM ให้ %s ไม่สำเร็จ (ไม่มี fcmToken/FCM ปิด)", user_id)
    return f"ส่งไม่สำเร็จ — แอปนี้ยังไม่มี fcmToken หรือ FCM ปิดอยู่ (corr_id: {corr_id})"
