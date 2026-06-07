"""
account — ลงทะเบียนแอป (รองรับ multi-user)

- register: แอปจับคู่ครั้งแรก (รหัสผ่านด่าน token guard มาแล้ว) → Hub จดแอปไว้

หมายเหตุ: การซิงก์ข้อมูล (kd/scenes/routines/profile) ย้ายไป REST แล้ว — ดู api/sync.py
(งานนั้นแอปยิงตรงๆ ไม่ผ่าน agent จึงไม่ต้องเป็น MCP tool)

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


def send_app_command(user_id: str, command: str, command_type: str, sender: str | None = None,
                     wait: bool = True) -> str:
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

    import hub_response

    corr_id = f"hub-cmd-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    prof = store.load_part(user_id, "profile") or {}
    assistant = prof.get("assistantName") or "ซิน"   # ใช้ชื่อผู้ช่วยจริงของคนรับ (ไม่ fix เป็น "ซิน")
    title = f"{assistant}มีข้อความถึงคุณ" if command_type == "chat" else "Hub ฝากงานให้ทำ"
    body = command if len(command) <= 120 else command[:117] + "..."

    # ลงทะเบียนรอผลก่อนส่ง (กันผลกลับมาเร็วกว่าจะได้ลงทะเบียน)
    if wait:
        hub_response.arm(corr_id, user_id)
    sent = fcm_push.send(user_id, title, body, {
        "corr_id": corr_id,
        "user_id": user_id,   # ให้ App แนบกลับมาตอนตอบ ACK เพื่อยืนยันว่าตอบ "คำสั่งนี้" ของ "user นี้" จริง
        "sender": sender,
        "type": command_type,
        ("text" if command_type == "chat" else "action_prompt"): command,
    })
    if not sent:
        _log.warning("ส่ง FCM ให้ %s ไม่สำเร็จ (ไม่มี fcmToken/FCM ปิด)", user_id)
        return f"ส่งไม่สำเร็จ — แอปนี้ยังไม่มี fcmToken หรือ FCM ปิดอยู่ (corr_id: {corr_id})"

    _log.info("ส่ง FCM (%s) ให้ %s: %s", command_type, user_id, command[:80])
    if not wait:   # เช่น automation รายงานผลกลับ — ส่งแล้วจบ ไม่ต้องรอผลตอบ
        return f"ส่งให้แอปผ่าน FCM แล้ว (corr_id: {corr_id})"
    # รอผลกลับจากแอป (App publish hub_response ตอนทำเสร็จ — เฉพาะตอนแอปเปิดอยู่)
    # action ใช้เวลานานกว่า (แอปต้องรัน agent) → รอนานกว่า chat
    timeout = 45 if command_type == "action" else 15
    res = hub_response.collect(corr_id, timeout)
    if res is None:
        return f"ส่งให้แอปแล้ว แต่ปลายทางยังไม่ตอบกลับ (อาจพับแอปอยู่ จะทำให้ตอนเปิดแอป) — corr_id: {corr_id}"
    head = "ปลายทางทำให้แล้ว" if res["ok"] else "ปลายทางทำไม่สำเร็จ"
    return f"{head}: {res['detail']}"
