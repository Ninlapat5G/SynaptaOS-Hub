# SynaptaHub — Web GUI (handoff plan สำหรับ Gemini)

> เอกสารส่งต่องาน. เป้าหมาย: เพิ่ม **หน้าเว็บตั้งค่า Hub** ที่ฝังในตัว Hub เอง
> ใช้สำหรับตั้งค่าระบบ, **คุยกับ agent ของ Hub ตรงผ่านเว็บ**, และ **อ่าน/แก้ไขข้อมูลผู้ใช้** ในเบราว์เซอร์
> เหมาะตอนตั้ง Hub ครั้งแรกบน Raspberry Pi 5 / ดูแลหลายผู้ใช้

อ่าน `plan_mcp.md` ก่อน (โดยเฉพาะ §4, §8.5) เพื่อเข้าใจสถาปัตยกรรม Hub ปัจจุบัน

---

## 0. สรุปสิ่งที่มีอยู่แล้ว (อย่าทำซ้ำ)

Hub เป็น Python (รันด้วย `python310` บนเครื่อง dev นี้ — Windows; production = RPi5/Linux) มีไฟล์:
- `main.py` — entry: `discovery.start()` + `server.run()`
- `server.py` — สร้าง `FastMCP("SynaptaHub")`, `build_app()` คืน **Starlette app** (จาก `mcp.streamable_http_app()`) ห่อด้วย `TokenGuard` middleware, `run()` รันด้วย uvicorn ที่ `config.MCP_HOST:config.MCP_PORT` (ดีฟอลต์ 0.0.0.0:8765), path MCP = `/mcp`
- `config.py` — ค่าจาก `.env`: `MCP_HOST/MCP_PORT/MCP_TOKEN`, `LLM_*` (DGX gemma), `MQTT_*`, `AGENT_NAME`, `DATA_DIR`
- `agent.py` — `run(task, os_type=None, ..., user_id=None) -> str` (ReAct, ชี้ DGX gemma). มี blocking I/O (langgraph stream)
- `store.py` — **ที่เก็บข้อมูลต่อ user** (ใช้อันนี้! อย่าเขียนใหม่):
  - `PARTS = ("profile","kd","scenes","routines","phone")`
  - `register_user(user_id, app_name, profile=None) -> dict`
  - `is_registered(user_id) -> bool`
  - `save_part(user_id, kind, data) -> None`  (data = dict/list, เขียน atomic)
  - `load_part(user_id, kind) -> data|None`
  - `list_users() -> dict`  (registry: {user_id: {app_name, last_seen, ...}})
  - โครงไฟล์: `data/registry.json`, `data/users/<user_id>/{profile,kd,scenes,routines,phone}.json`
- `osprofile.py` — คำสั่งตาม OS (portable)
- `tools/` — `os_exec, web_search, system_info, iot, task(run_task), automation, account(register/sync_data/get_user_data)`

deps มีแล้ว: `mcp`, `uvicorn`, `starlette`, `langgraph`, `langchain-openai`, `paho-mqtt`, `psutil`, `python-dotenv`, `requests`. **Starlette มากับ mcp อยู่แล้ว** — ใช้ route/StaticFiles ของ Starlette ได้เลย ไม่ต้องลง Flask/FastAPI เพิ่ม

---

## 1. หลักการออกแบบ (ทำตามนี้)

1. **เสิร์ฟจาก process เดียวกับ Hub** — ไม่เปิด server ใหม่. mount route เพิ่มบน Starlette app ที่ `server.build_app()` คืนมา
2. **Frontend = static ล้วน ไม่มี build step** (vanilla HTML/JS/CSS + `fetch`). เหตุผล: ต้องรันบน RPi ที่ไม่มี node toolchain — เปิดไฟล์เสิร์ฟตรงๆ จบ
3. **ไม่ทำลายของเดิม**: route `/mcp` กับ `TokenGuard` ต้องทำงานเหมือนเดิม. **สำคัญ**: ตอนนี้ `TokenGuard.dispatch` เช็ค token กับ **ทุก request** — ต้องแก้ให้เช็คเฉพาะ path ที่ขึ้นต้น `/mcp` ไม่งั้นมันจะบล็อกหน้า `/admin` ด้วย. ส่วน `/admin` ใช้ auth ของตัวเอง (ดู §4)
4. **เก็บข้อมูลผ่าน `store.py` เท่านั้น** — web อ่าน/แก้ผ่าน store ไม่แตะไฟล์ตรง
5. **คุย agent** = เรียก `agent.run(task, user_id=...)` แต่มัน blocking → ต้องรันใน thread: `await asyncio.to_thread(agent.run, task, user_id=uid)` (กัน event loop ค้าง)

---

## 2. ไฟล์ที่จะเพิ่ม

```
SynaptaOS-Hub/
  webadmin.py            # Starlette routes ของ /admin + /admin/api/*
  web/
    index.html           # SPA หน้าเดียว
    app.js               # logic: login, users, edit data, chat
    style.css            # ธีมเข้มให้เข้ากับแบรนด์ (ฟ้า #00D4FF / ม่วง #B44FFF / พื้นหลัง #080B12)
```

แก้ `config.py`: เพิ่ม `ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")` (ว่าง = ไม่เช็ค, เหมาะตอน dev/local). เพิ่มใน `.env.example` ด้วย
แก้ `server.py`: mount routes ของ webadmin + แก้ TokenGuard ให้เช็คเฉพาะ `/mcp`

---

## 3. Backend — `webadmin.py` (spec)

ใช้ `starlette.routing.Route`, `starlette.responses.JSONResponse/FileResponse`, `starlette.staticfiles.StaticFiles`.

API (ทั้งหมดอยู่ใต้ `/admin/api`, ตอบ JSON):

| Method | Path | ทำอะไร | backend |
|---|---|---|---|
| GET  | `/admin` | เสิร์ฟ `web/index.html` | FileResponse |
| GET  | `/admin/api/users` | รายชื่อ user ทั้งหมด | `store.list_users()` |
| GET  | `/admin/api/users/{uid}/{kind}` | อ่านข้อมูล 1 ส่วน | `store.load_part(uid, kind)` (kind ต้องอยู่ใน `store.PARTS`) |
| PUT  | `/admin/api/users/{uid}/{kind}` | บันทึกข้อมูล 1 ส่วน (body = JSON) | `store.save_part(uid, kind, body)` |
| POST | `/admin/api/agent` | คุยกับ agent. body `{task, user_id?}` | `await asyncio.to_thread(agent.run, task, user_id=user_id)` → `{reply}` |
| GET  | `/admin/api/system` | ข้อมูลระบบ + รายชื่อ tool | `system_info.snapshot_text()` + `await mcp.list_tools()` (ชื่อ+desc) |

- validate `kind` กับ `store.PARTS` (กัน path แปลก), `uid` ปล่อยให้ `store._safe` จัดการ (มันมีอยู่แล้ว)
- ทุก route ใต้ `/admin/api` → เช็ค admin auth ก่อน (ดู §4)
- เสิร์ฟ static `web/app.js`, `web/style.css` ผ่าน `StaticFiles` ที่ mount `/admin/static` หรือ route ตรง

แก้ `server.py` — ตัวอย่างทิศทาง:
```python
# server.py
from starlette.routing import Mount, Route
import webadmin

def build_app():
    app = mcp.streamable_http_app()       # มี route /mcp อยู่แล้ว
    app.add_middleware(TokenGuard)          # << แก้ TokenGuard ให้เช็คเฉพาะ path /mcp
    webadmin.mount(app, mcp)               # เพิ่ม routes /admin*, ส่ง mcp ไปให้เรียก list_tools
    return app
```
> หมายเหตุ: Starlette app ที่ FastMCP คืนมา เพิ่ม route ทีหลังทำได้ผ่าน `app.router.routes.append(...)` หรือ `app.add_route(...)`. ตรวจ API เวอร์ชันจริงด้วย `python310 -c "import server; print(type(server.build_app()))"`

TokenGuard เดิม (server.py) แก้เป็น:
```python
async def dispatch(self, request, call_next):
    if config.MCP_TOKEN and request.url.path.startswith("/mcp"):
        ... # เช็คเหมือนเดิม
    return await call_next(request)
```

---

## 4. Auth ของ /admin

- ใช้ `config.ADMIN_TOKEN`. ถ้าว่าง = ไม่เช็ค (dev/local). ถ้าตั้ง = ทุก `/admin/api/*` ต้องมี header `Authorization: Bearer <ADMIN_TOKEN>`
- หน้าเว็บ: ถ้าโดน 401 → โชว์หน้า login ให้กรอก token → เก็บใน `localStorage` → แนบ header ทุก fetch
- production บน RPi แนะนำตั้ง ADMIN_TOKEN. (ถ้าจะเข้มกว่านี้: bind admin เฉพาะ localhost — ทำทีหลังได้)

---

## 5. Frontend — `web/` (spec)

SPA หน้าเดียว 3 แท็บ:

1. **ผู้ใช้ (Users)**
   - ซ้าย: รายชื่อ user จาก `/admin/api/users` (โชว์ app_name + last_seen)
   - คลิก user → ขวา: แท็บย่อย profile/kd/scenes/routines/phone
   - แต่ละส่วน: โหลด JSON มาโชว์ใน `<textarea>` (หรือ JSON editor เบาๆ) + ปุ่ม **บันทึก** → PUT กลับ. validate ว่าเป็น JSON ก่อนส่ง โชว์ ✓/✗
2. **คุยกับระบบ (Agent)**
   - ช่องเลือก user (optional) + ช่องพิมพ์คำสั่ง → POST `/admin/api/agent` → โชว์ reply. โชว์สถานะ "กำลังคิด…" ระหว่างรอ
3. **ระบบ (System)**
   - โชว์ `/admin/api/system`: OS/CPU/RAM/disk + ตารางรายชื่อ tool ที่ Hub มี

สไตล์: พื้นหลังเข้ม (#080B12), accent ฟ้า/ม่วง, การ์ดขอบบาง โปร่งนิดๆ ให้เข้าธีม "Deep Glass" ของแอปมือถือ. ใช้ system font ได้ ไม่ต้องโหลด font ภายนอก (RPi อาจ offline)

ทั้งหมดใช้ `fetch` + `async/await`, ไม่ต้องมี framework. ถ้าจะใช้ก็ได้แค่ CDN เบาๆ (เช่น petite-vue/Alpine) แต่ vanilla พอ

---

## 6. ทดสอบ (ทำให้ครบ)

```
# ฝั่ง Hub
python310 main.py            # หรือเฉพาะ web: python310 -c "import server,uvicorn; uvicorn.run(server.build_app(),host='127.0.0.1',port=8765)"
# เปิดเบราว์เซอร์ http://localhost:8765/admin
```
เช็ค:
- [ ] `/mcp` ยังทำงาน (App เดิมต่อได้, token guard ยัง 401/200 เหมือนเดิม) — อย่าให้ web ไปทำพัง
- [ ] เห็นรายชื่อ user (สร้าง user ทดสอบ: `python310 -c "import store; store.register_user('u1','test'); store.save_part('u1','kd',[{'name':'ไฟ','topic':'home/light'}])"`)
- [ ] แก้ kd ในเว็บ → บันทึก → reload เห็นค่าใหม่ (เช็คไฟล์ `data/users/u1/kd.json`)
- [ ] คุย agent ผ่านเว็บได้ (ต้องต่อ DGX gemma ได้ — เครื่อง dev นี้มี Tailscale, `http://dgx:11434` เข้าถึงได้)
- [ ] ตั้ง `ADMIN_TOKEN` แล้ว ต้อง login ก่อน

---

## 7. ขอบเขต / สิ่งที่ "ยังไม่ต้องทำ"

- ไม่ต้องทำ realtime/websocket (chat ตอบทีเดียวพอ — streaming เก็บไว้ทีหลัง)
- ไม่ต้องทำ user management ซับซ้อน (ลบ user, สิทธิ์รายคน) — แค่ดู/แก้ข้อมูลพอ
- ไม่ต้อง build pipeline — static ล้วน
- กัน path traversal: `kind` ต้องอยู่ใน `store.PARTS`, `uid` ผ่าน `store._safe` (มีแล้ว)

## 8. นิสัยโค้ดของโปรเจกต์ (ทำตาม)
- เขียนให้ง่ายที่สุด ไม่ over-engineer, ไม่ใส่ abstraction/error-handling สำหรับ scenario ที่ยังไม่เกิด
- comment ภาษาไทยสั้นๆ ตามสไตล์ไฟล์อื่น
- รันคำสั่ง Python ด้วย `python310`
- commit + push ขึ้น `github.com/Ninlapat5G/SynaptaOS-Hub` เมื่อเสร็จแต่ละก้อน
