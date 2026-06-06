import sys
import ssl
import time
import json
import logging
import threading
from pathlib import Path
import paho.mqtt.client as mqtt

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_log = logging.getLogger("simulator")

sys.path.append(str(Path(__file__).resolve().parent))
import config
import store

print("="*60)
print("SynaptaOS Dynamic Device Simulator")
print(f"Broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
print(f"Base Topic: {config.MQTT_BASE}")
print("="*60)

devices_state = {}
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sim-livingroom-node")
client_lock = threading.Lock()

def get_configured_devices():
    """ดึงข้อมูลอุปกรณ์ทั้งหมดจาก store ทุกคน"""
    devices = {}
    for uid in store.list_users():
        kd = store.load_part(uid, "kd") or []
        for d in kd:
            topic = d.get("topic")
            if topic and d.get("type") != "hub":
                devices[topic] = d
    return devices

def publish_manifest():
    if not client or not client.is_connected():
        return
    manifest_topic = config.topic("nodes/sim-livingroom-node/manifest")
    manifest_devices = []
    
    devices = get_configured_devices()
    for topic, d in devices.items():
        manifest_devices.append({
            "topic": topic,
            "name": d.get("name", topic),
            "type": d.get("type", "digital"),
            "configured": True,
            "stateTopic": config.topic(f"{topic}/state"),
            "cmdTopic": config.topic(f"{topic}/set"),
            "configTopic": config.topic(f"{topic}/config")
        })
    manifest = {
        "nodeId": "sim-livingroom-node",
        "baseTopic": config.MQTT_BASE,
        "fw": "1.0.0-sim",
        "devices": manifest_devices
    }
    client.publish(manifest_topic, json.dumps(manifest, ensure_ascii=False), qos=1, retain=True)
    _log.info(f"Published manifest to {manifest_topic} with {len(manifest_devices)} devices")

def publish_states():
    with client_lock:
        if not client or not client.is_connected():
            return
        for dev_topic, val in list(devices_state.items()):
            state_topic = config.topic(f"{dev_topic}/state")
            client.publish(state_topic, val, qos=1, retain=True, properties={"message_expiry_interval": 300})
            _log.info(f"Published state: {state_topic} = {val}")

def scan_devices():
    """แสกนหาอุปกรณ์ใหม่และยกเลิกอุปกรณ์ที่ถูกลบ"""
    global devices_state
    if not client or not client.is_connected():
        return
        
    devices = get_configured_devices()
    changed = False
    
    # ค้นหาอุปกรณ์ใหม่
    for topic, d in devices.items():
        if topic not in devices_state:
            t_type = d.get("type", "digital")
            if t_type == "analog":
                devices_state[topic] = "0"
            elif t_type == "sensor":
                devices_state[topic] = "25.0"
            else:
                devices_state[topic] = "false"
            _log.info(f"[New Device] Discovered {topic} ({t_type})")
            
            # Subscribe CMD topic
            cmd_topic = config.topic(f"{topic}/set")
            client.subscribe(cmd_topic, qos=1)
            _log.info(f"Subscribed to command: {cmd_topic}")
            
            # Publish initial state
            state_topic = config.topic(f"{topic}/state")
            client.publish(state_topic, devices_state[topic], qos=1, retain=True, properties={"message_expiry_interval": 300})
            changed = True
            
    # ลบอุปกรณ์ที่ไม่มีในฐานข้อมูลแล้วออกจากการติดตาม
    for topic in list(devices_state.keys()):
        if topic not in devices:
            _log.info(f"[Delete Device] Removed {topic}")
            cmd_topic = config.topic(f"{topic}/set")
            client.unsubscribe(cmd_topic)
            del devices_state[topic]
            changed = True
            
    if changed:
        publish_manifest()

def scan_loop():
    """เธรดเบื้องหลังสแกนการเปลี่ยนแปลงของอุปกรณ์ทุกๆ 4 วินาที"""
    while True:
        try:
            scan_devices()
        except Exception as e:
            _log.error(f"Error in scan_loop: {e}")
        time.sleep(4)

def on_connect(c, u, flags, rc, props=None):
    _log.info(f"Connected to broker with code {rc}")
    
    # Publish Node Status
    status_topic = config.topic("nodes/sim-livingroom-node/status")
    c.publish(status_topic, "online", qos=1, retain=True)
    _log.info(f"Published status: online to {status_topic}")
    
    # ดึงอุปกรณ์ที่มีอยู่มา subscribe
    devices = get_configured_devices()
    subs = []
    for topic, d in devices.items():
        t_type = d.get("type", "digital")
        if topic not in devices_state:
            if t_type == "analog":
                devices_state[topic] = "0"
            elif t_type == "sensor":
                devices_state[topic] = "25.0"
            else:
                devices_state[topic] = "false"
        subs.append((config.topic(f"{topic}/set"), 1))
        
    if subs:
        c.subscribe(subs)
        _log.info(f"Subscribed to command topics: {[s[0] for s in subs]}")
        
    publish_manifest()
    publish_states()

def on_message(c, u, msg):
    payload = msg.payload.decode("utf-8")
    _log.info(f"Received message on {msg.topic}: {payload}")
    
    topic = msg.topic
    if config.MQTT_BASE and topic.startswith(config.MQTT_BASE + "/"):
        topic = topic[len(config.MQTT_BASE) + 1:]
    
    if topic.endswith("/set"):
        rel_topic = topic[:-4]
        if rel_topic in devices_state:
            devices_state[rel_topic] = payload
            # ส่งสถานะกลับไปยัง MQTT state topic
            state_topic = config.topic(f"{rel_topic}/state")
            c.publish(state_topic, payload, qos=1, retain=True, properties={"message_expiry_interval": 300})
            _log.info(f"Updated and published state: {state_topic} = {payload}")

client.on_connect = on_connect
client.on_message = on_message

if config.MQTT_USE_TLS:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    client.tls_set_context(context)

try:
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=30)
    
    # เริ่มต้น Thread สแกนอุปกรณ์แบบ dynamic
    t = threading.Thread(target=scan_loop, daemon=True)
    t.start()
    
    print("Simulator running dynamically. Press Ctrl+C to stop.")
    client.loop_forever()
except KeyboardInterrupt:
    print("\nStopping simulator...")
    status_topic = config.topic("nodes/sim-livingroom-node/status")
    client.publish(status_topic, "offline", qos=1, retain=True)
    client.disconnect()
    print("Stopped.")
except Exception as e:
    _log.error(f"Simulator error: {e}")

