"""
SynaptaOS Hub — entry point

1. discovery.start()  → broadcast endpoint (IP:port) ผ่าน MQTT retained
2. server.run()       → FastMCP streamable-http บน Tailscale IP (block จนปิด)
"""

import logging
import threading

import config
import log
import discovery
import telemetry
import device_state
import hub_response
import pipeline
import events
import server
from tools import system_info, automation

_log = logging.getLogger("hub")


def _auto_open_admin():
    """เด้งหน้า admin ขึ้นเบราว์เซอร์เมื่อ "ระบบพร้อม" — HTTP server ฟังพอร์ตแล้ว + ต่อ broker แล้ว

    ปิดได้ด้วย AUTO_OPEN_ADMIN=false (เช่นบน RPi headless ที่ไม่มีจอ)
    """
    import socket
    import time
    import webbrowser

    if config.env_value("AUTO_OPEN_ADMIN", "true").strip().lower() != "true":
        return

    port = config.MCP_PORT

    def _port_up() -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False

    # 1) รอ uvicorn ขึ้นฟังพอร์ต (ไม่เกิน 60 วิ)
    deadline = time.time() + 60
    while time.time() < deadline and not _port_up():
        time.sleep(0.5)
    if not _port_up():
        _log.warning("auto-open: server ไม่ขึ้นใน 60 วิ — ข้ามการเปิดเบราว์เซอร์")
        return

    # 2) รอ broker ต่อติด (best-effort 30 วิ — เกินเวลาก็เปิดอยู่ดี เพราะ admin ใช้ได้)
    bdl = time.time() + 30
    while time.time() < bdl and not hub_response.is_connected():
        time.sleep(0.5)

    url = f"http://127.0.0.1:{port}/admin"
    _log.info("ระบบพร้อม → เปิดหน้า admin: %s (broker=%s)",
              url, "ต่อแล้ว" if hub_response.is_connected() else "ยังไม่ต่อ")
    try:
        webbrowser.open(url)
    except Exception as e:
        _log.warning("auto-open: เปิดเบราว์เซอร์ไม่ได้ (%s) — เปิดเองที่ %s", e, url)


def main():
    log.setup()
    print("SynaptaOS Hub (MCP)")
    print(f"  LLM    : {config.LLM_MODEL} @ {config.LLM_BASE_URL}")
    print(f"  MQTT   : {config.MQTT_BROKER}:{config.MQTT_PORT}{'  [TLS]' if config.MQTT_USE_TLS else ''}")
    print(f"  Agent  : {config.AGENT_NAME}")
    print()
    print(system_info.snapshot_text())
    print()
    _log.info("Hub เริ่มทำงาน")

    # บริการ MQTT/พื้นหลัง (connect broker นานได้) → สตาร์ตใน thread แยก ให้ uvicorn (MCP server)
    # ขึ้นทันทีพร้อมกัน ไม่ต้องรอ broker ก่อน — App เลยต่อ MCP ได้เร็ว ไม่ค้างรอตอนบูต
    def _start_services():
        for name, fn in (
            ("discovery", discovery.start),
            ("telemetry", telemetry.start),
            ("devstate", device_state.start),
            ("hub_response", hub_response.start),
            ("pipeline", pipeline.start),
            ("events", events.start),
            ("automation", automation.start),
        ):
            try:
                fn()
            except Exception as e:
                _log.error("%s start ล้มเหลว: %s", name, e)

    threading.Thread(target=_start_services, daemon=True).start()
    threading.Thread(target=_auto_open_admin, daemon=True).start()  # พร้อมแล้วเด้งหน้า admin เอง

    try:
        server.run()   # uvicorn (MCP) — ขึ้นทันที ขนานกับบริการพื้นหลังด้านบน
    finally:
        automation.stop()
        events.stop()
        pipeline.stop()
        hub_response.stop()
        device_state.stop()
        telemetry.stop()
        discovery.stop()


if __name__ == "__main__":
    main()
