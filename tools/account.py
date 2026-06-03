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
