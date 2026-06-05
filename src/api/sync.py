"""sync — แอปส่งข้อมูล (kd/scenes/routines/profile) มาเก็บที่ Hub ตรงๆ (REST, ไม่ผ่าน agent)

ย้ายมาจาก MCP tool 'sync_data' เดิม — งานนี้แอปยิงเองตรงๆ ไม่เกี่ยวกับ agent จึงเป็น REST พอ
"""
import json

from starlette.responses import JSONResponse

import store


def register(api):
    @api.post("/sync")
    async def sync_data(request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)

        user_id = store._safe(body.get("user_id", ""))
        kind = body.get("kind", "")
        if not user_id or kind not in store.PARTS:
            return JSONResponse({"error": "invalid user_id or kind"}, status_code=400)
        if not store.is_registered(user_id):
            return JSONResponse({"error": "not registered"}, status_code=409)

        raw = body.get("data_json", "")
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return JSONResponse({"error": "invalid data_json"}, status_code=400)

        store.save_part(user_id, kind, data)
        return JSONResponse({"ok": True, "kind": kind})
