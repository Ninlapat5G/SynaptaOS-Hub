"""
discovery — บอก App ว่า Hub อยู่ IP ไหน ผ่าน MQTT (retained)

อยู่วง Tailscale เดียวกัน = เชื่อใจกันแล้ว → ไม่มี pairing code/token แลกกัน
แค่ broadcast endpoint: App (subscribe อยู่แล้ว) เห็น online + host:port → ต่อ MCP ตรง

retained message ข้ามเน็ตได้ (ต่างจาก mDNS ที่ Tailscale ไม่ส่ง multicast)
"""

import json
import logging
import socket
import subprocess
import threading
import time

import paho.mqtt.client as mqtt

import config

_log = logging.getLogger("discovery")
_client: mqtt.Client | None = None
_stop = threading.Event()
_started_at = 0  # epoch ตอน Hub เริ่มรอบนี้ — App เห็นค่าเปลี่ยน = Hub restart → ดึง tools ใหม่
_zeroconf = None  # ตัวประกาศชื่อ mDNS — เก็บไว้ไม่ให้โดน GC ระหว่างรัน

# republish online ทุกกี่วิ — สั้นกว่า keepalive (30) เพื่อให้สถานะใน broker สดเสมอ
# และถ้า LWT เคยเด้ง offline ไว้ heartbeat ตัวถัดไปจะ republish online ทับให้ทันที
HEARTBEAT_SEC = 15


_cached_ip = None


def tailscale_ip() -> str:
    """อ่าน Tailscale IPv4 (100.x). หาไม่เจอ → fallback เป็น LAN IP ของเครื่อง"""
    global _cached_ip
    if _cached_ip:
        return _cached_ip

    ip = ""
    try:
        out = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        ip = out.splitlines()[0].strip() if out else ""
    except Exception:
        pass

    if not ip:
        # fallback — เครื่องไม่มี tailscale (เช่นตอน dev/test)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"

    _cached_ip = ip
    return ip


def _status_payload(status: str, host: str) -> str:
    return json.dumps({"status": status, "host": host, "port": config.MCP_PORT, "started_at": _started_at})


def _lan_ip() -> str:
    """IP ฝั่ง LAN (interface ที่เป็นเส้นทางออกเน็ต) — สำหรับให้บอร์ดในวง LAN หาเจอ"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _register_mdns() -> None:
    """ประกาศชื่อ synapta-hub.local → IP ปัจจุบันของเครื่องนี้ (mDNS)

    บอร์ด ESP32 ตั้ง broker เป็นชื่อนี้แทน IP — DHCP แจกเลขใหม่ก็ยังหาเจอ
    บน Raspberry Pi โค้ดเดิมนี้ใช้ได้เลย (หรือจะพึ่ง Avahi ของระบบก็ได้)
    """
    global _zeroconf
    try:
        from zeroconf import Zeroconf, ServiceInfo
        ip = _lan_ip()
        info = ServiceInfo(
            "_mqtt._tcp.local.",
            "SynaptaOS Hub._mqtt._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=config.MQTT_PORT,
            server="synapta-hub.local.",
        )
        _zeroconf = Zeroconf()
        _zeroconf.register_service(info)
        _log.info("mDNS: ประกาศ synapta-hub.local → %s:%s", ip, config.MQTT_PORT)
    except Exception as e:
        _log.warning("mDNS ลงทะเบียนไม่ได้ (บอร์ดต้องใช้ IP ตรง ๆ แทน): %s", e)


def start() -> None:
    """connect broker, ตั้ง LWT offline, publish retained online + endpoint"""
    global _client, _started_at
    _started_at = int(time.time())
    host = tailscale_ip()
    status_topic = config.topic(f"hub/{config.AGENT_NAME}/status")
    _register_mdns()   # ให้บอร์ดหา broker เจอด้วยชื่อ synapta-hub.local (กัน DHCP ย้าย IP)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(c, u, flags, rc, props=None):
        c.publish(status_topic, _status_payload("online", host), qos=1, retain=True)
        _log.info("เชื่อม broker + ประกาศ online %s → host=%s port=%s", status_topic, host, config.MCP_PORT)

    def on_disconnect(c, u, disconnect_flags, rc, props=None):
        _log.warning("หลุดจาก broker (rc=%s) — paho จะต่อใหม่ให้เอง", rc)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
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
    if _zeroconf:
        try:
            _zeroconf.close()
        except Exception:
            pass
    if _client:
        host = tailscale_ip()
        status_topic = config.topic(f"hub/{config.AGENT_NAME}/status")
        _client.publish(status_topic, _status_payload("offline", host), qos=1, retain=True)
        _client.loop_stop()
        _client.disconnect()
