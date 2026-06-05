"""
device_state — Hub sub สถานะอุปกรณ์ IoT ตรงจาก MQTT แล้วเก็บเป็นไฟล์ (Hub = ตัวกลาง)

อุปกรณ์ (Node) publish สถานะที่ {base}/{topic}/state — แต่ retained หมดอายุใน 5 นาที
Hub sub topic พวกนี้ตาม kd ของทุก user แล้วเก็บค่าล่าสุดลงไฟล์ → รู้สถานะสดเองโดย:
  - แอปไม่ต้องรีเลย์สถานะอุปกรณ์ขึ้นมา (ประหยัดพลังงานตอนพับ/background)
  - ข้อมูลอยู่รอดแม้ปิด Hub/อุปกรณ์เงียบ (ไม่พึ่ง retained อย่างเดียว)
  - โหลดเข้าแรมครั้งเดียวตอนเปิด ไม่ต้องอ่านไฟล์ทุกครั้งที่ agent ถาม

topic อุปกรณ์อยู่ใน namespace MQTT รวม (ไม่ผูกกับ user คนใดคนหนึ่ง) → เก็บไฟล์เดียว
ที่ data/devstate.json คีย์ด้วย topic. แยกเป็น client ของตัวเอง subscribe ค้างไว้
"""

import json
import logging
import os
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

import config
import store

_log = logging.getLogger("devstate")

_client: mqtt.Client | None = None
_state: dict[str, dict] = {}     # device topic (relative) → {"value": str, "ts": int}
_subscribed: set[str] = set()    # state topic เต็มที่ sub ไปแล้ว
_lock = threading.Lock()
_dirty = False

_FILE = Path(config.DATA_DIR) / "devstate.json"


def _load() -> None:
    global _state
    try:
        _state = json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        _state = {}


def _save() -> None:
    global _dirty
    with _lock:
        if not _dirty:
            return
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, _FILE)  # atomic
        _dirty = False


def _flush_loop() -> None:
    """เขียนลงดิสก์เป็นระยะ (ไม่เกินทุก 10 วิ) — coalesce การเปลี่ยนถี่ ๆ ของ sensor ไม่ให้เขียนรัว"""
    _save()
    t = threading.Timer(10, _flush_loop)
    t.daemon = True
    t.start()


def _state_topic(device_topic: str) -> str:
    return config.topic(f"{device_topic}/state")


def _device_topics() -> set[str]:
    """รวม topic อุปกรณ์ของทุก user จาก kd (ข้าม hub — ไม่มี /state)"""
    topics = set()
    for uid in store.list_users():
        kd = store.load_part(uid, "kd") or []
        for d in kd:
            t = d.get("topic")
            if t and d.get("type") != "hub":
                topics.add(t)
    return topics


def _resync() -> None:
    """sub topic ใหม่ที่เพิ่งโผล่ใน kd, ยกเลิก topic ที่หายไป"""
    if _client is None:
        return
    want = {_state_topic(t) for t in _device_topics()}
    for st in want - _subscribed:
        _client.subscribe(st, qos=1)
        _subscribed.add(st)
    for st in _subscribed - want:
        _client.unsubscribe(st)
        _subscribed.discard(st)


def _rel_topic(state_topic: str) -> str | None:
    """{base}/{device_topic}/state → device_topic"""
    t = state_topic
    if config.MQTT_BASE and t.startswith(config.MQTT_BASE + "/"):
        t = t[len(config.MQTT_BASE) + 1:]
    if t.endswith("/state"):
        return t[: -len("/state")]
    return None


def start() -> None:
    global _client
    _load()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(c, u, flags, rc, props=None):
        _subscribed.clear()  # reconnect = broker ลืม sub หมด → sub ใหม่ตาม kd ปัจจุบัน
        _resync()
        _log.info("เชื่อม broker + subscribe %d device topics (โหลดจากไฟล์ %d ค่า)", len(_subscribed), len(_state))

    def on_disconnect(c, u, disconnect_flags, rc, props=None):
        _log.warning("หลุดจาก broker (rc=%s) — paho จะต่อใหม่ให้เอง", rc)

    def on_message(c, u, msg):
        global _dirty
        rel = _rel_topic(msg.topic)
        if rel is None:
            return
        try:
            val = msg.payload.decode("utf-8")
        except Exception:
            return
        cur = _state.get(rel)
        if cur and cur.get("value") == val:
            return  # ค่าเดิม ไม่ต้อง mark dirty
        _state[rel] = {"value": val, "ts": int(time.time())}
        _dirty = True
        _log.info("อุปกรณ์ %s = %s", rel, val)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    if config.MQTT_USE_TLS:
        import ssl
        client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=30)
    client.loop_start()
    _client = client
    _flush_loop()

    # kd เปลี่ยน (แอป sync มาใหม่) หรือ user ถูกลบ → sub topic ใหม่ตาม
    store.add_listener(lambda uid, kind, data: _resync() if kind in ("kd", "delete") else None)


def get(device_topic: str) -> str | None:
    """ค่าสถานะล่าสุดของอุปกรณ์ (None = ยังไม่เคยรู้จัก)"""
    e = _state.get(device_topic)
    return e.get("value") if e else None


def stop() -> None:
    _save()  # flush ครั้งสุดท้ายก่อนปิด
    if _client:
        _client.loop_stop()
        _client.disconnect()
