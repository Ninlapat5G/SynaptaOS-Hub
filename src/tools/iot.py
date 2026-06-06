"""
iot — tool ให้ agent ของ Hub สั่งอุปกรณ์ IoT เอง (ฐานของ automation/rules)

publish MQTT แบบ one-shot (connect→publish→disconnect) — stateless ไม่ถือ connection ค้าง
Node (ESP32) เกาะ broker เดียวกันผ่าน LAN
"""

import paho.mqtt.publish as publish

import config


def publish_set(topic: str, value: str) -> str:
    """publish ค่าไปยัง {base}/{topic}/set"""
    full = config.topic(f"{topic}/set")
    
    # พยายามใช้ client ที่เชื่อมต่ออยู่แล้วเพื่อส่งทันที (ความเร็วระดับ ~10ms บายพาสการทำ TLS handshake ใหม่)
    try:
        import device_state
        if device_state._client and device_state._client.is_connected():
            device_state._client.publish(full, value, qos=1)
            return f"[iot] set {full} = {value} (shared client)"
    except Exception:
        pass

    tls  = {"tls_version": 2} if config.MQTT_USE_TLS else None
    try:
        publish.single(
            full,
            payload=value,
            hostname=config.MQTT_BROKER,
            port=config.MQTT_PORT,
            qos=1,
            tls=tls,
        )
        return f"[iot] set {full} = {value} (fallback)"
    except Exception as e:
        return f"[iot error] {e}"


# ── MCP tool ─────────────────────────────────────────────────────────────────
def register(mcp):
    @mcp.tool()
    def set_device(topic: str, value: str) -> str:
        """สั่งอุปกรณ์ IoT ผ่าน MQTT เช่น topic='bedroom/lamp', value='on'. publish ไปที่ {topic}/set"""
        return publish_set(topic, value)
