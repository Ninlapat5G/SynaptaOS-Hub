"""
log — ตั้งค่า logging กลางของ Hub

ทุกบรรทัด log จะมี เวลา + ระดับ + ชื่อโมดูล → ไล่ debug ฝั่ง Hub ได้ง่าย
(เห็นว่าอะไรเกิดตอนไหน เช่น MQTT หลุด/ต่อใหม่ตอนกี่โมง, ได้ telemetry จากใคร, ส่ง FCM เมื่อไหร่)

ใช้: import log แล้วเรียก log.setup() ครั้งเดียวตอนเริ่ม · โมดูลอื่นใช้ logging.getLogger(ชื่อ)
"""

import logging


def setup() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
