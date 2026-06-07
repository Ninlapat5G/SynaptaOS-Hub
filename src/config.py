"""
Hub config — settings ทั้งหมดอ่านจาก .env รวมไว้ที่เดียว

ใช้แทนการกระจาย os.getenv() ตามไฟล์ต่างๆ เพื่อให้รู้ว่ามี knob อะไรบ้างในที่เดียว
"""

import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# ── LLM (ชี้ไป DGX gemma ผ่าน Tailscale) ─────────────────────────────────────
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://dgx:11434/v1")
LLM_MODEL    = os.getenv("LLM_MODEL",    "gemma4:26b")
LLM_API_KEY  = os.getenv("LLM_API_KEY",  "ollama")  # Ollama ไม่เช็ค key แต่ client ต้องมีค่า

# ── MCP server (หน้าบ้านใหม่ — App ต่อผ่าน Tailscale IP) ──────────────────────
MCP_HOST  = os.getenv("MCP_HOST", "0.0.0.0")   # bind ทุก interface → เข้าถึงผ่าน IP 100.x ของ Tailscale ได้
MCP_PORT  = int(os.getenv("MCP_PORT", "8765"))
MCP_PATH  = os.getenv("MCP_PATH", "/mcp")

_ENV_FILE = Path(__file__).resolve().parent / ".env"

def get_admin_token() -> str:
    """ดึงรหัสผ่านผู้ดูแลระบบล่าสุดจากไฟล์ .env โดยตรงเพื่อรองรับการเปลี่ยนแปลงโดยไม่ต้องเริ่มระบบใหม่"""
    load_dotenv(_ENV_FILE, override=True)
    return os.getenv("ADMIN_TOKEN", "")

def get_mcp_token() -> str:
    """ดึงรหัสผ่านแอปมือถือล่าสุดจากไฟล์ .env โดยตรง"""
    load_dotenv(_ENV_FILE, override=True)
    return os.getenv("MCP_TOKEN", "")


def env_value(key: str, default: str = "") -> str:
    """อ่านค่าล่าสุดจาก .env แบบสด — สำหรับค่าที่แก้ผ่านเว็บแล้วอยากให้มีผลทันที (hot)"""
    load_dotenv(_ENV_FILE, override=True)
    return os.getenv(key, default)


# ── ค่า hot (อ่านสดทุกครั้ง = แก้ผ่านเว็บแล้วมีผลเลย ไม่ต้อง restart) ──
def get_session_ttl_sec() -> int:
    try:
        return max(60, int(env_value("SESSION_TTL_MIN", "30")) * 60)
    except Exception:
        return 1800


def get_session_max() -> int:
    try:
        return max(1, int(env_value("SESSION_MAX_MSGS", "10")))
    except Exception:
        return 10


def get_command_timeout() -> float:
    try:
        return float(env_value("COMMAND_TIMEOUT", "60"))
    except Exception:
        return 60.0

# ── MQTT (App↔Node + Hub broadcast discovery) — แยกขาดจาก Tailscale ──────────
MQTT_BROKER  = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() == "true"
MQTT_BASE    = os.getenv("MQTT_BASE_TOPIC", "").rstrip("/")

# ── Identity ─────────────────────────────────────────────────────────────────
AGENT_NAME = os.getenv("AGENT_NAME", "office-pc")

# ── Storage (ข้อมูลต่อ user — เก็บแยกไฟล์ รองรับ multi-user) ──────────────────
DATA_DIR = os.getenv("DATA_DIR") or str(Path(__file__).resolve().parent / "data")

# ── FCM (ช่องสำรองเด้งหาแอป เมื่อ MQTT ส่งไม่ถึง / Hub อยากส่งตรง) ────────────
# path ไปไฟล์ service account JSON ของ Firebase — ว่าง = ปิดการใช้ FCM
# ใส่แค่ชื่อไฟล์ก็ได้ (จะอ้างอิงจากโฟลเดอร์ src/ นี้) หรือใส่ path เต็มก็ได้
_fcm = os.getenv("FCM_CREDENTIALS", "")
if _fcm and not os.path.isabs(_fcm):
    _fcm = str(Path(__file__).resolve().parent / _fcm)
FCM_CREDENTIALS = _fcm

# ── Agent pipeline (thread pool + task queue — รองรับหลาย user พร้อมกันแบบมี backpressure) ──
# AGENT_WORKERS = เพดาน concurrency "ต่อ Hub ตัวนี้" (รันงาน agent พร้อมกันได้กี่งาน)
# ตั้ง 4 ไม่ใช่ 8 (=OLLAMA_NUM_PARALLEL ของ DGX) เพราะ DGX แชร์กันหลาย Hub ในบ้าน →
# กัน Hub ตัวเดียวกินไม่เกิน 4 slot เหลือเผื่อ Hub อื่น และ 1 Hub แทบไม่ทำเกิน 4 พร้อมกันอยู่แล้ว
# เกินเพดานก็จ่อคิวไป (ดู AGENT_QUEUE_MAX) ไม่ถล่ม DGX
AGENT_WORKERS   = int(os.getenv("AGENT_WORKERS", "4"))
AGENT_QUEUE_MAX = int(os.getenv("AGENT_QUEUE_MAX", "100")) # คิวงานสูงสุด (เต็ม = ปฏิเสธ/รอ ไม่ spawn ไม่จำกัด)

# ── Misc ─────────────────────────────────────────────────────────────────────
COMMAND_TIMEOUT = float(os.getenv("COMMAND_TIMEOUT", "60"))
SERPER_API_KEY  = os.getenv("SERPER_API_KEY", "")

_OS_MAP = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}
OS_TYPE = os.getenv("OS_TYPE") or _OS_MAP.get(platform.system(), "linux")


def topic(suffix: str) -> str:
    """สร้าง MQTT topic ที่ prefix ด้วย base — base ว่างก็คืน suffix เปล่า"""
    return f"{MQTT_BASE}/{suffix}" if MQTT_BASE else suffix
