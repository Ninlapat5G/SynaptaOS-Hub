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
MCP_TOKEN = os.getenv("MCP_TOKEN", "")          # ว่าง = ไม่เช็ค token (เชื่อ Tailscale ACL อย่างเดียว)
MCP_PATH  = os.getenv("MCP_PATH", "/mcp")

# ── MQTT (App↔Node + Hub broadcast discovery) — แยกขาดจาก Tailscale ──────────
MQTT_BROKER  = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() == "true"
MQTT_BASE    = os.getenv("MQTT_BASE_TOPIC", "").rstrip("/")

# ── Identity ─────────────────────────────────────────────────────────────────
AGENT_NAME = os.getenv("AGENT_NAME", "office-pc")

# ── Storage (ข้อมูลต่อ user — เก็บแยกไฟล์ รองรับ multi-user) ──────────────────
DATA_DIR = os.getenv("DATA_DIR") or str(Path(__file__).resolve().parent / "data")

# ── Misc ─────────────────────────────────────────────────────────────────────
COMMAND_TIMEOUT = float(os.getenv("COMMAND_TIMEOUT", "60"))
SERPER_API_KEY  = os.getenv("SERPER_API_KEY", "")

_OS_MAP = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}
OS_TYPE = os.getenv("OS_TYPE") or _OS_MAP.get(platform.system(), "linux")


def topic(suffix: str) -> str:
    """สร้าง MQTT topic ที่ prefix ด้วย base — base ว่างก็คืน suffix เปล่า"""
    return f"{MQTT_BASE}/{suffix}" if MQTT_BASE else suffix
