"""
ตัวอย่าง source แบบ request-style (HTTP) — ป้อนงานให้ agent ผ่าน pipeline

POST /api/pipeline   body: {task, user_id?, sinks?, wait?}
  - wait=true (ดีฟอลต์): รอผลแล้วตอบกลับใน HTTP response (= reply กลับแหล่งเดิม)
    + ถ้าระบุ sinks มาด้วย ก็ส่งผลเข้า sink เหล่านั้นพร้อมกัน
  - wait=false: ใส่งานเข้า queue แล้วตอบ 202 ทันที — ผลไปออกที่ sinks ที่ระบุ (เช่น ['fcm'])

= แม่แบบ "แหล่งข้อมูลอื่น → agent → output (ทั้ง reply และ/หรือ sink, แล้วแต่ task)"
"""
import asyncio

from starlette.responses import JSONResponse

import pipeline
from pipeline.task import AgentTask


def register(api):
    @api.post("/pipeline")
    async def submit_task(request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "body ต้องเป็น JSON"}, status_code=400)

        task = (body.get("task") or "").strip()
        if not task:
            return JSONResponse({"error": "task ว่าง"}, status_code=400)
        user_id = body.get("user_id") or None
        sinks = body.get("sinks") or []
        wait = body.get("wait", True)

        if wait:
            # รอผล → ตอบกลับแหล่งเดิม (HTTP response). รันใน thread กัน block event loop ของ server
            result = await asyncio.to_thread(
                pipeline.run_sync, task, user_id=user_id, source="http", history=[], sinks=sinks)
            return JSONResponse({"ok": True, "result": result})

        # fire-and-forget → ผลไปออกที่ sinks (เช่น เด้ง FCM หาแอป user)
        ok = pipeline.submit(AgentTask(task=task, user_id=user_id, source="http",
                                       history=[], sinks=sinks))
        return JSONResponse({"ok": ok, "queued": ok}, status_code=202 if ok else 503)
