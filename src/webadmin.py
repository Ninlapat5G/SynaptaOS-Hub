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

active_websockets = []
main_loop = None

def broadcast_device_state(topic: str, state: str):
    """ส่งข้อมูลสถานะอุปกรณ์ที่เปลี่ยนไปหาเบราว์เซอร์ทุกตัวแบบ Real-time ทันที"""
    import json
    payload = json.dumps({
        "type": "device_update",
        "topic": topic,
        "state": state
    }, ensure_ascii=False)
    
    loop = main_loop
    if not loop:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
            
    async def do_broadcast():
        for ws in list(active_websockets):
            try:
                await ws.send_text(payload)
            except Exception:
                if ws in active_websockets:
                    active_websockets.remove(ws)
                    
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(do_broadcast(), loop)

def mount(app, mcp):
    """ทำการเชื่อมโยงเส้นทางของหน้าเว็บควบคุมเข้ากับ Starlette App"""

    def capture_loop():
        global main_loop
        try:
            main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    # Starlette รุ่นใหม่ (1.x) ถอด decorator @app.route/@app.websocket_route ออกแล้ว
    # ใช้ add_route/add_websocket_route แทน — ห่อเป็น decorator เล็กๆ เพื่อคงรูปแบบโค้ดเดิม
    def route(path, methods=["GET"]):
        def deco(fn):
            app.add_route(path, fn, methods=methods)
            return fn
        return deco

    def ws_route(path):
        def deco(fn):
            app.router.add_websocket_route(path, fn)
            return fn
        return deco

    # 1. หน้ากากควบคุมหลัก
    @route("/admin", methods=["GET"])
    async def admin_page(request):
        index_file = WEB_DIR / "index.html"
        if not index_file.exists():
            return JSONResponse({"error": "Admin static files not initialized yet."}, status_code=404)
        return FileResponse(str(index_file))

    # 2. API ดึงรายชื่อผู้ใช้ทั้งหมด
    @route("/admin/api/users", methods=["GET"])
    async def api_list_users(request):
        capture_loop()
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        users = store.list_users()
        return JSONResponse(users)

    # API ลบผู้ใช้ออก
    @route("/admin/api/users/{uid}", methods=["DELETE"])
    async def api_delete_user(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        uid = request.path_params.get("uid", "")
        uid_safe = store._safe(uid)
        success = store.delete_user(uid_safe)
        if success:
            return JSONResponse({"status": "deleted"})
        else:
            return JSONResponse({"error": "failed to delete user"}, status_code=500)

    # 3. API ดึงข้อมูลส่วนย่อยของผู้ใช้
    @route("/admin/api/users/{uid}/{kind}", methods=["GET"])
    async def api_get_user_part(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        uid = request.path_params.get("uid", "")
        kind = request.path_params.get("kind", "")
        if kind not in store.PARTS:
            return JSONResponse({"error": "invalid part"}, status_code=400)
        
        uid_safe = store._safe(uid)
        data = store.load_part(uid_safe, kind)
        if kind == "kd" and isinstance(data, list):
            import device_state
            for d in data:
                st = device_state.get(d.get("topic", ""))
                if st is not None:
                    d["state"] = st
        return JSONResponse(data)

    # 4. API บันทึกข้อมูลส่วนย่อยของผู้ใช้
    @route("/admin/api/users/{uid}/{kind}", methods=["PUT"])
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

    # API ส่งข้อความ/คำสั่งไปที่แอปผู้ใช้ผ่าน FCM
    @route("/admin/api/users/{uid}/message", methods=["POST"])
    async def api_send_message_to_user(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        uid = request.path_params.get("uid", "")
        uid_safe = store._safe(uid)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
        
        message = body.get("message", "")
        cmd_type = body.get("type", "chat")
        if not message:
            return JSONResponse({"error": "message is required"}, status_code=400)
            
        from tools import account
        res = account.send_app_command(uid_safe, message, cmd_type, sender="admin_web")
        return JSONResponse({"status": "sent", "result": res})

    # 5. API คุยกับเอเจนต์แบบสลับเธรด (Thread) เพื่อป้องกันไม่ให้เซิร์ฟเวอร์ค้าง
    @route("/admin/api/agent", methods=["POST"])
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
        history = body.get("history") or []  # ประวัติบทสนทนาก่อนหน้า (multi-turn memory)

        # เรียกเอเจนต์ด้วย asyncio.to_thread เพื่อไม่ให้กีดกันการทำงานของ Event Loop
        reply = await asyncio.to_thread(agent.run, task, user_id=user_id_safe, history=history)
        return JSONResponse({"reply": reply})

    # 6. API ข้อมูลระบบหลักและเครื่องมือเชื่อมต่อ (MCP Tools)
    @route("/admin/api/system", methods=["GET"])
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
    @route("/admin/api/settings/passwords", methods=["GET"])
    async def api_get_passwords(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse({
            "admin_token_set": bool(config.get_admin_token()),
            "mcp_token": config.get_mcp_token()
        })

    # 8. API อัปเดตรหัสผ่านใหม่ลงไฟล์ .env
    @route("/admin/api/settings/passwords", methods=["POST"])
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

    # API ควบคุมอุปกรณ์ IoT ผ่าน MQTT
    @route("/admin/api/devices/control", methods=["POST"])
    async def api_control_device(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
        
        topic = body.get("topic")
        value = body.get("value")
        if not topic or value is None:
            return JSONResponse({"error": "topic and value are required"}, status_code=400)
            
        from tools.iot import publish_set
        res = publish_set(topic, str(value))
        return JSONResponse({"status": "sent", "result": res})

    # API ดึงข้อมูลอุปกรณ์ทั้งหมดของทุกผู้ใช้ พร้อมสถานะล่าสุด
    @route("/admin/api/devices", methods=["GET"])
    async def api_list_all_devices(request):
        if not verify_token(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        import store
        import device_state
        
        all_devices = []
        for uid in store.list_users():
            kd = store.load_part(uid, "kd") or []
            prof = store.load_part(uid, "profile") or {}
            user_name = prof.get("displayName") or prof.get("app_name") or uid
            for d in kd:
                if d.get("type") == "hub":
                    continue
                topic = d.get("topic", "")
                st = device_state.get(topic)
                all_devices.append({
                    "uid": uid,
                    "userName": user_name,
                    "topic": topic,
                    "name": d.get("name", topic),
                    "room": d.get("room", "ทั่วไป"),
                    "type": d.get("type", "digital"),
                    "icon": d.get("icon", "plug"),
                    "unit": d.get("unit", ""),
                    "state": st
                })
        return JSONResponse(all_devices)

    # 9. Real-time WebSockets
    from starlette.websockets import WebSocket, WebSocketDisconnect
    import json
    
    @ws_route("/admin/ws")
    async def websocket_endpoint(websocket: WebSocket):
        capture_loop()
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

    @ws_route("/admin/ws/agent")
    async def websocket_agent_endpoint(websocket: WebSocket):
        capture_loop()
        token = websocket.query_params.get("token", "")
        admin_token = config.get_admin_token()
        if admin_token and token != admin_token:
            await websocket.close(code=4003)
            return

        await websocket.accept()
        try:
            while True:
                msg_text = await websocket.receive_text()
                data = json.loads(msg_text)
                task = data.get("task", "")
                user_id = data.get("user_id")
                user_id_safe = store._safe(user_id) if user_id else None
                history = data.get("history") or []
                
                try:
                    async for event in agent.astream_run(task, user_id_safe, history):
                        await websocket.send_text(json.dumps(event, ensure_ascii=False))
                except Exception as e:
                    await websocket.send_text(json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False))
        except WebSocketDisconnect:
            pass

    def broadcast_update(user_id: str, kind: str, data):
        loop = main_loop
        if not loop:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    return
        
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
                        
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(do_broadcast(), loop)
            
    store.add_listener(broadcast_update)

    # 10. ผูกโฟลเดอร์เก็บไฟล์เว็บนิ่ง (Static Files)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/admin/static", StaticFiles(directory=str(WEB_DIR)), name="admin_static")
