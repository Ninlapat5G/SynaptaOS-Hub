"""
settings_schema — แหล่งความจริงเดียวของ "ค่าตั้งระบบที่แก้ผ่านเว็บ admin ได้"

แต่ละ field:
  key     : ชื่อตัวแปรใน .env
  label   : ชื่อที่โชว์ในเว็บ
  type    : "str" | "int" | "bool"
  hot     : True = แก้แล้วมีผลทันที (โค้ดอ่านค่าสด) · False = ต้อง restart Hub ก่อนถึงมีผล
  secret  : True = ค่าอ่อนไหว (เว็บโชว์ masked, เว้นว่าง = ไม่เปลี่ยน)
  default : ค่าเริ่มต้นถ้า .env ไม่ได้ตั้ง
  help    : คำอธิบายสั้น (ไม่บังคับ)

หมายเหตุ: ADMIN_TOKEN / MCP_TOKEN ไม่อยู่ที่นี่ — อยู่แท็บ "ความปลอดภัย" แยกต่างหาก
(กันแก้พลาดแล้วล็อกตัวเองออกจากระบบ)
"""

CATEGORIES = [
    {"id": "llm", "label": "🧠 LLM (สมองของ agent — DGX/Ollama)", "fields": [
        {"key": "LLM_BASE_URL", "label": "Base URL", "type": "str", "hot": False, "default": "http://dgx:11434/v1"},
        {"key": "LLM_MODEL", "label": "โมเดล", "type": "str", "hot": False, "default": "gemma4:26b"},
        {"key": "LLM_API_KEY", "label": "API Key", "type": "str", "hot": False, "secret": True, "default": "ollama"},
    ]},
    {"id": "agent", "label": "⚙️ Agent Pipeline & ความจำ", "fields": [
        {"key": "AGENT_WORKERS", "label": "จำนวน worker (รันพร้อมกัน)", "type": "int", "hot": False, "default": "4",
         "help": "เพดานต่อ Hub — ปกติ ≤ OLLAMA_NUM_PARALLEL ของ DGX"},
        {"key": "AGENT_QUEUE_MAX", "label": "ขนาดคิวงานสูงสุด", "type": "int", "hot": False, "default": "100"},
        {"key": "COMMAND_TIMEOUT", "label": "timeout คำสั่ง (วินาที)", "type": "int", "hot": True, "default": "60"},
        {"key": "SESSION_TTL_MIN", "label": "ความจำบทสนทนา: หมดอายุ (นาที)", "type": "int", "hot": True, "default": "30"},
        {"key": "SESSION_MAX_MSGS", "label": "ความจำบทสนทนา: เก็บกี่ข้อความ", "type": "int", "hot": True, "default": "10"},
    ]},
    {"id": "mcp", "label": "🔌 MCP Server (ช่องที่ App ต่อเข้ามา)", "fields": [
        {"key": "MCP_HOST", "label": "Host (bind)", "type": "str", "hot": False, "default": "0.0.0.0"},
        {"key": "MCP_PORT", "label": "Port", "type": "int", "hot": False, "default": "8765"},
        {"key": "MCP_PATH", "label": "Path", "type": "str", "hot": False, "default": "/mcp"},
    ]},
    {"id": "mqtt", "label": "📡 MQTT (IoT / discovery / telemetry)", "fields": [
        {"key": "MQTT_BROKER", "label": "Broker", "type": "str", "hot": False, "default": "broker.hivemq.com"},
        {"key": "MQTT_PORT", "label": "Port", "type": "int", "hot": False, "default": "1883"},
        {"key": "MQTT_USE_TLS", "label": "ใช้ TLS", "type": "bool", "hot": False, "default": "false"},
        {"key": "MQTT_BASE_TOPIC", "label": "Base topic (prefix)", "type": "str", "hot": False, "default": ""},
    ]},
    {"id": "fcm", "label": "🔔 FCM (เด้ง push หาแอป)", "fields": [
        {"key": "FCM_CREDENTIALS", "label": "ไฟล์ service account (path/ชื่อไฟล์)", "type": "str", "hot": False,
         "default": "", "help": "เว้นว่าง = ปิด FCM"},
    ]},
    {"id": "search", "label": "🔎 Web Search", "fields": [
        {"key": "SERPER_API_KEY", "label": "Serper API Key", "type": "str", "hot": False, "secret": True, "default": ""},
    ]},
    {"id": "system", "label": "🖥️ ระบบ / Identity", "fields": [
        {"key": "AGENT_NAME", "label": "ชื่อ Hub (agent name)", "type": "str", "hot": False, "default": "office-pc"},
        {"key": "OS_TYPE", "label": "ระบบปฏิบัติการ (เว้นว่าง = auto)", "type": "str", "hot": False, "default": ""},
        {"key": "DATA_DIR", "label": "โฟลเดอร์เก็บข้อมูล (เว้นว่าง = ค่าปริยาย)", "type": "str", "hot": False, "default": ""},
    ]},
]


def all_fields():
    for cat in CATEGORIES:
        for f in cat["fields"]:
            yield f


def field_map() -> dict:
    return {f["key"]: f for f in all_fields()}
