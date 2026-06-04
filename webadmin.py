"""
Web Admin Backend — จัดการเส้นทางการทำงานของหน้าควบคุมระบบ /admin และ APIs ที่เกี่ยวข้อง
"""

import asyncio
from pathlib import Path
from starlette.responses import JSONResponse, FileResponse
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
import store
import agent
import config
from tools import system_info

HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"

def verify_token(request: Request) -> bool:
    """ตรวจสอบความถูกต้องของ ADMIN_TOKEN"""
    admin_token = config.get_admin_token()
    if not admin_token:
        return True
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth[:7].lower() == "bearer " else ""
    return token == admin_token

def mount(app, mcp):
    """ทำการเชื่อมโยงเส้นทางของหน้าเว็บควบคุมเข้ากับ Starlette App"""

    # 1. หน้ากากควบคุมหลัก
    @app.route("/admin", methods=["GET"])
    async def admin_page(request):
        index_file = WEB_DIR / "index.html"
        if not index_file.exists():
            return JSONResponse({"error": "Admin static files not initialized yet."}, status_code=404)
        return FileResponse(str(index_file))

    # 2. API ดึงรายชื่อผู้ใช้ทั้งหมด
    @app.route("/admin/api/users", methods=["GET"])
    async def api_list_users(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        users = store.list_users()
        return JSONResponse(users)

    # 3. API ดึงข้อมูลส่วนย่อยของผู้ใช้
    @app.route("/admin/api/users/{uid}/{kind}", methods=["GET"])
    async def api_get_user_part(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        uid = request.path_params.get("uid", "")
        kind = request.path_params.get("kind", "")
        if kind not in store.PARTS:
            return JSONResponse({"error": "invalid part"}, status_code=400)
        
        uid_safe = store._safe(uid)
        data = store.load_part(uid_safe, kind)
        return JSONResponse(data)

    # 4. API บันทึกข้อมูลส่วนย่อยของผู้ใช้
    @app.route("/admin/api/users/{uid}/{kind}", methods=["PUT"])
    async def api_put_user_part(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        uid = request.path_params.get("uid", "")
        kind = request.path_params.get("kind", "")
        if kind not in store.PARTS:
            return JSONResponse({"error": "invalid part"}, status_code=400)
        
        uid_safe = store._safe(uid)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
            
        store.save_part(uid_safe, kind, body)
        return JSONResponse({"status": "saved"})

    # 5. API คุยกับเอเจนต์แบบสลับเธรด (Thread) เพื่อป้องกันไม่ให้เซิร์ฟเวอร์ค้าง
    @app.route("/admin/api/agent", methods=["POST"])
    async def api_agent_chat(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
            
        task = body.get("task", "")
        if not task:
            return JSONResponse({"error": "task is required"}, status_code=400)
            
        user_id = body.get("user_id")
        user_id_safe = store._safe(user_id) if user_id else None
        
        # เรียกเอเจนต์ด้วย asyncio.to_thread เพื่อไม่ให้กีดกันการทำงานของ Event Loop
        reply = await asyncio.to_thread(agent.run, task, user_id=user_id_safe)
        return JSONResponse({"reply": reply})

    # 6. API ข้อมูลระบบหลักและเครื่องมือเชื่อมต่อ (MCP Tools)
    @app.route("/admin/api/system", methods=["GET"])
    async def api_system_info(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
            
        sys_text = system_info.snapshot_text()
        tools_list = []
        try:
            tools = await mcp.list_tools()
            for t in tools:
                tools_list.append({
                    "name": t.name,
                    "description": t.description or ""
                })
        except Exception as e:
            tools_list = [{"name": "error", "description": str(e)}]
            
        return JSONResponse({
            "system_info": sys_text,
            "tools": tools_list
        })

    # 7. API ดึงค่าการตั้งค่ารหัสผ่านปัจจุบัน
    @app.route("/admin/api/settings/passwords", methods=["GET"])
    async def api_get_passwords(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse({
            "admin_token_set": bool(config.get_admin_token()),
            "mcp_token": config.get_mcp_token()
        })

    # 8. API อัปเดตรหัสผ่านใหม่ลงไฟล์ .env
    @app.route("/admin/api/settings/passwords", methods=["POST"])
    async def api_change_passwords(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
            
        old_token_input = body.get("old_admin_token", "")
        new_admin_token = body.get("new_admin_token", "")
        new_mcp_token = body.get("new_mcp_token", "")
        
        current_admin_token = config.get_admin_token()
        # ถ้าปัจจุบันมีตั้งรหัสไว้ ต้องเช็ครหัสเดิมก่อน
        if current_admin_token and old_token_input != current_admin_token:
            return JSONResponse({"error": "incorrect old password"}, status_code=403)
            
        # บันทึกค่าใหม่ลงไฟล์ .env
        import dotenv
        env_file = Path(config.__file__).resolve().parent / ".env"
        
        try:
            dotenv.set_key(str(env_file), "ADMIN_TOKEN", new_admin_token)
            dotenv.set_key(str(env_file), "MCP_TOKEN", new_mcp_token)
        except Exception as e:
            return JSONResponse({"error": f"Failed to save settings: {str(e)}"}, status_code=500)
            
        return JSONResponse({"status": "updated"})

    # 9. Real-time WebSockets
    from starlette.websockets import WebSocket, WebSocketDisconnect
    import json
    
    active_websockets: list[WebSocket] = []
    
    @app.websocket_route("/admin/ws")
    async def websocket_endpoint(websocket: WebSocket):
        token = websocket.query_params.get("token", "")
        admin_token = config.get_admin_token()
        if admin_token and token != admin_token:
            await websocket.close(code=4003)
            return
            
        await websocket.accept()
        active_websockets.append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in active_websockets:
                active_websockets.remove(websocket)

    def broadcast_update(user_id: str, kind: str, data):
        loop = asyncio.get_event_loop()
        
        async def do_broadcast():
            payload = json.dumps({
                "type": "update",
                "user_id": user_id,
                "kind": kind,
                "data": data
            }, ensure_ascii=False)
            
            for ws in list(active_websockets):
                try:
                    await ws.send_text(payload)
                except Exception:
                    if ws in active_websockets:
                        active_websockets.remove(ws)
                        
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(do_broadcast(), loop)
            
    store.add_listener(broadcast_update)

    # 10. ผูกโฟลเดอร์เก็บไฟล์เว็บนิ่ง (Static Files)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/admin/static", StaticFiles(directory=str(WEB_DIR)), name="admin_static")
