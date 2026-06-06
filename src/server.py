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
from tools import task, account, automation
for mod in (task, account, automation):
    mod.register(mcp)


# ── Token guard ──────────────────────────────────────────────────────────────
class TokenGuard(BaseHTTPMiddleware):
    """ตรวจ token ใน header ถ้า config.MCP_TOKEN ถูกตั้งไว้ — ไม่ตั้ง = ปล่อยผ่าน (เช็คเฉพาะ path /mcp)"""

    async def dispatch(self, request, call_next):
        mcp_token = config.get_mcp_token()
        if mcp_token and request.url.path.startswith("/mcp"):
            auth = request.headers.get("authorization", "")
            token = auth[7:] if auth[:7].lower() == "bearer " else request.headers.get("x-synapta-token", "")
            if token != mcp_token:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def build_app():
    """คืน Starlette app ของ streamable-http พร้อม token guard ครอบ + REST API (app→hub) + หน้าเว็บควบคุม"""
    app = mcp.streamable_http_app()
    app.add_middleware(TokenGuard)
    import webadmin
    import api
    webadmin.mount(app, mcp)
    api.mount(app)  # REST endpoint ฝั่งแอป (/api/*) — งานที่ไม่ผ่าน agent เช่น sync ข้อมูล
    return app


def run():
    import uvicorn
    from discovery import tailscale_ip
    ip = tailscale_ip()
    print(f"[Hub] MCP server → http://{config.MCP_HOST}:{config.MCP_PORT}{config.MCP_PATH}")
    print(f"[Hub] Admin panel available at: http://{ip}:{config.MCP_PORT}/admin")
    print(f"[Hub] token guard: {'ON' if config.get_mcp_token() else 'OFF (Tailscale ACL only)'}")
    # log_config=None → uvicorn ไม่ตั้ง logging ของตัวเองทับ → log ของ uvicorn propagate
    # ไปที่ root ที่เราตั้งไว้ (มี timestamp+วันที่) เหมือน log ส่วนอื่นของ Hub
    uvicorn.run(build_app(), host=config.MCP_HOST, port=config.MCP_PORT,
                log_level="info", log_config=None)
