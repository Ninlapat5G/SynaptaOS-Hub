"""
SynaptaOS Hub — entry point

1. discovery.start()  → broadcast endpoint (IP:port) ผ่าน MQTT retained
2. server.run()       → FastMCP streamable-http บน Tailscale IP (block จนปิด)
"""

import logging

import config
import log
import discovery
import telemetry
import device_state
import server
from tools import system_info

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

    try:
        discovery.start()
    except Exception as e:
        _log.error("discovery start ล้มเหลว (broadcast ปิด): %s", e)

    try:
        telemetry.start()
    except Exception as e:
        _log.error("telemetry start ล้มเหลว (phone telemetry ปิด): %s", e)

    try:
        device_state.start()
    except Exception as e:
        _log.error("devstate start ล้มเหลว (live device state ปิด): %s", e)

    try:
        server.run()
    finally:
        device_state.stop()
        telemetry.stop()
        discovery.stop()


if __name__ == "__main__":
    main()
