"""
account — ลงทะเบียนแอป + ซิงก์ข้อมูลผู้ใช้ (รองรับ multi-user)

- register: แอปจับคู่ครั้งแรก (รหัสผ่านด่าน token guard มาแล้ว) → Hub จดแอปไว้
- sync_data: แอปส่งข้อมูล (kd/scenes/routines/phone/profile) มาเก็บ — ส่งเฉพาะตอนเปลี่ยน
- get_user_data: อ่านข้อมูล 1 ส่วนของ user (ให้ agent หยิบเฉพาะที่ต้องใช้ ไม่เปลือง context)

ทุก tool รับ user_id เพราะ MCP over HTTP เป็น stateless — แอปแนบ id ของตัวเองมาทุกครั้ง
"""

import json

import store


def register(mcp):
    @mcp.tool()
    def register(user_id: str, app_name: str) -> str:
        """ลงทะเบียนแอปกับ Hub (จับคู่ครั้งแรก). user_id = รหัสประจำแอป, app_name = ชื่อที่โชว์. Hub จะจดไว้เพื่อให้สั่งงานและเก็บข้อมูลแยกตามผู้ใช้"""
        r = store.register_user(user_id, app_name)
        return json.dumps({"ok": True, **r}, ensure_ascii=False)

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

    @mcp.tool()
    def get_user_data(user_id: str, kind: str) -> str:
        """อ่านข้อมูล 1 ส่วนของผู้ใช้จาก Hub. kind = kd|scenes|routines|phone|profile. คืน JSON string (ไม่มีข้อมูล = null)"""
        try:
            data = store.load_part(user_id, kind)
        except ValueError as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        return json.dumps({"ok": True, "kind": kind, "data": data}, ensure_ascii=False)

    @mcp.tool()
    def send_command_to_user_app(user_query: str, command: str, command_type: str) -> str:
        """ส่งคำสั่งหรือข้อความแชทไปยังแอปมือถือของผู้ใช้ผ่าน MQTT โดยวิเคราะห์ค้นหาจากข้อมูลโปรไฟล์ (ไม่ใช่ user_id ตรงๆ)
        - user_query: ชื่อจริง ชื่อเล่น หรือข้อมูลใน bio เพื่อค้นหาผู้ใช้ที่ต้องการ
        - command: ข้อความที่จะคุย หรือคำสั่งสั่งงาน
        - command_type: 'chat' (ส่งข้อความคุยในแชทให้แอปตอบ) หรือ 'action' (ส่งคำสั่งเพื่อให้แอปทำงานเงียบๆ เบื้องหลัง)
        """
        uid = find_user_by_query(user_query)
        if not uid:
            return json.dumps({"ok": False, "error": f"ไม่พบผู้ใช้ที่ตรงกับคำค้นหา: '{user_query}'"}, ensure_ascii=False)
        
        prof = store.load_part(uid, "profile") or {}
        display_name = prof.get("displayName") or prof.get("app_name") or uid

        res = send_mqtt_app_command(uid, command, command_type)
        return json.dumps({"ok": True, "user_id": uid, "display_name": display_name, "result": res}, ensure_ascii=False)


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


def send_mqtt_app_command(user_id: str, command: str, command_type: str, sender: str = "hub") -> str:
    import json
    import time
    import uuid
    import paho.mqtt.publish as publish
    import config
    
    corr_id = f"hub-cmd-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    payload = {
        "corr_id": corr_id,
        "sender": sender,
        "type": command_type,
        "payload": {
            "text" if command_type == "chat" else "action_prompt": command
        },
        "timestamp": int(time.time())
    }
    
    topic = f"users/{user_id}/hub_cmd"
    full_topic = config.topic(topic)
    tls = {"tls_version": 2} if config.MQTT_USE_TLS else None
    
    try:
        publish.single(
            full_topic,
            payload=json.dumps(payload, ensure_ascii=False),
            hostname=config.MQTT_BROKER,
            port=config.MQTT_PORT,
            qos=1,
            tls=tls,
        )
        return f"ส่งคำสั่งแบบ {command_type} ไปที่ {full_topic} สำเร็จ (corr_id: {corr_id})"
    except Exception as e:
        return f"ล้มเหลว (ไม่สามารถส่งคำสั่งผ่าน MQTT: {e})"
