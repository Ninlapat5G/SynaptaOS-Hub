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
import hub_response
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
        hub_response.start()
    except Exception as e:
        _log.error("hub_response start ล้มเหลว (รับผลกลับจากแอปปิด): %s", e)

    try:
        automation.start()
    except Exception as e:
        _log.error("automation start ล้มเหลว (งานอัตโนมัติ Hub ปิด): %s", e)

    try:
        server.run()
    finally:
        automation.stop()
        hub_response.stop()
        device_state.stop()
        telemetry.stop()
        discovery.stop()


if __name__ == "__main__":
    main()
