"""
discovery — บอก App ว่า Hub อยู่ IP ไหน ผ่าน MQTT (retained)

อยู่วง Tailscale เดียวกัน = เชื่อใจกันแล้ว → ไม่มี pairing code/token แลกกัน
แค่ broadcast endpoint: App (subscribe อยู่แล้ว) เห็น online + host:port → ต่อ MCP ตรง

retained message ข้ามเน็ตได้ (ต่างจาก mDNS ที่ Tailscale ไม่ส่ง multicast)
"""

import json
import socket
import subprocess
import threading
import time

import paho.mqtt.client as mqtt

import config

_client: mqtt.Client | None = None
_stop = threading.Event()
_started_at = 0  # epoch ตอน Hub เริ่มรอบนี้ — App เห็นค่าเปลี่ยน = Hub restart → ดึง tools ใหม่

# republish online ทุกกี่วิ — สั้นกว่า keepalive (30) เพื่อให้สถานะใน broker สดเสมอ
# และถ้า LWT เคยเด้ง offline ไว้ heartbeat ตัวถัดไปจะ republish online ทับให้ทันที
HEARTBEAT_SEC = 15


def tailscale_ip() -> str:
    """อ่าน Tailscale IPv4 (100.x). หาไม่เจอ → fallback เป็น LAN IP ของเครื่อง"""
    try:
        out = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        ip = out.splitlines()[0].strip() if out else ""
        if ip:
            return ip
    except Exception:
        pass
    # fallback — เครื่องไม่มี tailscale (เช่นตอน dev/test)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _status_payload(status: str, host: str) -> str:
    return json.dumps({"status": status, "host": host, "port": config.MCP_PORT, "started_at": _started_at})


def start() -> None:
    """connect broker, ตั้ง LWT offline, publish retained online + endpoint"""
    global _client, _started_at
    _started_at = int(time.time())
    host = tailscale_ip()
    status_topic = config.topic(f"hub/{config.AGENT_NAME}/status")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(c, u, flags, rc, props=None):
        c.publish(status_topic, _status_payload("online", host), qos=1, retain=True)
        print(f"[discovery] broadcast {status_topic} → host={host} port={config.MCP_PORT}")

    client.on_connect = on_connect
    # LWT — broker publish offline ให้เองถ้า Hub หลุดกะทันหัน
    client.will_set(status_topic, _status_payload("offline", host), qos=1, retain=True)

    if config.MQTT_USE_TLS:
        import ssl
        client.tls_set(cert_reqs=ssl.CERT_NONE)

    client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=30)
    client.loop_start()
    _client = client

    # heartbeat — republish online retained เรื่อย ๆ ตราบเท่าที่ Hub ยังรัน
    # กันสถานะใน broker ค้างเป็น offline (จาก LWT ตอนเน็ตหลุดแว้บ) ทั้งที่ Hub ยังออนไลน์
    _stop.clear()

    def _heartbeat():
        while not _stop.wait(HEARTBEAT_SEC):
            try:
                client.publish(status_topic, _status_payload("online", host), qos=1, retain=True)
            except Exception:
                pass

    threading.Thread(target=_heartbeat, daemon=True).start()


def stop() -> None:
    _stop.set()
    if _client:
        host = tailscale_ip()
        status_topic = config.topic(f"hub/{config.AGENT_NAME}/status")
        _client.publish(status_topic, _status_payload("offline", host), qos=1, retain=True)
        _client.loop_stop()
        _client.disconnect()
