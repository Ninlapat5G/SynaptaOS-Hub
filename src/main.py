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
import server
from tools import system_info, automation

_log = logging.getLogger("hub")


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
            ("automation", automation.start),
        ):
            try:
                fn()
            except Exception as e:
                _log.error("%s start ล้มเหลว: %s", name, e)

    threading.Thread(target=_start_services, daemon=True).start()

    try:
        server.run()   # uvicorn (MCP) — ขึ้นทันที ขนานกับบริการพื้นหลังด้านบน
    finally:
        automation.stop()
        pipeline.stop()
        hub_response.stop()
        device_state.stop()
        telemetry.stop()
        discovery.stop()


if __name__ == "__main__":
    main()
