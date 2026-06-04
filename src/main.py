"""
SynaptaOS Hub — entry point

1. discovery.start()  → broadcast endpoint (IP:port) ผ่าน MQTT retained
2. server.run()       → FastMCP streamable-http บน Tailscale IP (block จนปิด)
"""

import config
import discovery
import telemetry
import server
from tools import system_info


def main():
    print("SynaptaOS Hub (MCP)")
    print(f"  LLM    : {config.LLM_MODEL} @ {config.LLM_BASE_URL}")
    print(f"  MQTT   : {config.MQTT_BROKER}:{config.MQTT_PORT}{'  [TLS]' if config.MQTT_USE_TLS else ''}")
    print(f"  Agent  : {config.AGENT_NAME}")
    print()
    print(system_info.snapshot_text())
    print()

    try:
        discovery.start()
    except Exception as e:
        print(f"[discovery] start failed (broadcast disabled): {e}")

    try:
        telemetry.start()
    except Exception as e:
        print(f"[telemetry] start failed (phone telemetry disabled): {e}")

    try:
        server.run()
    finally:
        telemetry.stop()
        discovery.stop()


if __name__ == "__main__":
    main()
