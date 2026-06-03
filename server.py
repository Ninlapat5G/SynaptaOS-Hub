"""
FastMCP server — หน้าบ้านใหม่ของ Hub (แทน MQTT loop เดิม)

- วนลงทะเบียน tool จากโฟลเดอร์ tools/ (เพิ่มฟีเจอร์ = วางไฟล์ + เติมชื่อใน TOOLS)
- รัน streamable-http bind 0.0.0.0 → เข้าถึงผ่าน Tailscale IP 100.x
- token guard บางๆ ใน HTTP header กันแอปแปลกในวง (ด่านหลักคือ Tailscale ACL)
"""

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import config

mcp = FastMCP("SynaptaHub", host=config.MCP_HOST, port=config.MCP_PORT)

# ── เมนู MCP — เพิ่มฟีเจอร์ = import โมดูลใหม่แล้วเติมชื่อในวง for ─────────────
from tools import os_exec, web_search, system_info, iot, task, automation
for mod in (os_exec, web_search, system_info, iot, task, automation):
    mod.register(mcp)


# ── Token guard ──────────────────────────────────────────────────────────────
class TokenGuard(BaseHTTPMiddleware):
    """ตรวจ token ใน header ถ้า config.MCP_TOKEN ถูกตั้งไว้ — ไม่ตั้ง = ปล่อยผ่าน"""

    async def dispatch(self, request, call_next):
        if config.MCP_TOKEN:
            auth = request.headers.get("authorization", "")
            token = auth[7:] if auth[:7].lower() == "bearer " else request.headers.get("x-synapta-token", "")
            if token != config.MCP_TOKEN:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def build_app():
    """คืน Starlette app ของ streamable-http พร้อม token guard ครอบ"""
    app = mcp.streamable_http_app()
    app.add_middleware(TokenGuard)
    return app


def run():
    import uvicorn
    print(f"[Hub] MCP server → http://{config.MCP_HOST}:{config.MCP_PORT}{config.MCP_PATH}")
    print(f"[Hub] token guard: {'ON' if config.MCP_TOKEN else 'OFF (Tailscale ACL only)'}")
    uvicorn.run(build_app(), host=config.MCP_HOST, port=config.MCP_PORT, log_level="info")
