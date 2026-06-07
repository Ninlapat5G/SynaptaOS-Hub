"""
REST API ฝั่งแอป (app→hub) — งานตรงๆ ที่ "ไม่ผ่าน agent" เช่น ซิงก์ข้อมูล
แยกออกจาก MCP (MCP เก็บไว้สำหรับงานที่ต้องให้ agent ทำ: run_task, list tools)

เพิ่ม endpoint ใหม่ = สร้างไฟล์ใน api/ ที่มี register(api) แล้วเติมชื่อในวง for ของ mount()
(แพทเทิร์นเดียวกับ tools/ ของ MCP — วางไฟล์ + เติมชื่อ)
"""
from starlette.responses import JSONResponse

import config


class Api:
    """ตัวช่วยลงทะเบียน route REST — ใส่ token guard (MCP_TOKEN ตัวเดียวกับ MCP) ให้อัตโนมัติ

    ใช้ผ่านเดคอเรเตอร์ในแต่ละโมดูล endpoint:  @api.post("/sync")  /  @api.get("/...")
    """

    def __init__(self, app, prefix="/api"):
        self.app = app
        self.prefix = prefix

    def _authorized(self, request) -> bool:
        required = config.get_mcp_token()
        if not required:
            return True  # ไม่ตั้ง token = พึ่ง Tailscale ACL อย่างเดียว (เหมือนฝั่ง MCP)
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth[:7].lower() == "bearer " else request.headers.get("x-synapta-token", "")
        return token == required

    def route(self, path, methods=("POST",)):
        def deco(fn):
            async def handler(request):
                if not self._authorized(request):
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                return await fn(request)

            self.app.add_route(self.prefix + path, handler, methods=list(methods))
            return fn

        return deco

    def post(self, path):
        return self.route(path, methods=("POST",))

    def get(self, path):
        return self.route(path, methods=("GET",))


def mount(app):
    """ลงทะเบียนทุก endpoint REST — เพิ่มฟีเจอร์ = import โมดูลใหม่แล้วเติมชื่อในวง for"""
    api = Api(app)
    from api import sync, pipeline
    for mod in (sync, pipeline):
        mod.register(api)
