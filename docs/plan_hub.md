# SynaptaHub — แผนพัฒนา (Rules Engine / Agent-to-Agent)

> เอกสารวางแผนพัฒนาฝั่ง Hub ต่อ — เป้าหมายคือให้ Hub กลายเป็น "สมองอัตโนมัติที่เปิดตลอด"
> รับ rule จากมือถือ (SynaptaOS app) แล้วเฝ้า event + ทำ action เอง = **Agent-to-Agent**
> (มือถือ = ผู้วาง/สั่ง · Hub = ผู้เฝ้า+ลงมือ)

---

## 1. สถานะปัจจุบัน (SynaptaHub-V0)

- **Python LangGraph ReAct agent** รันบน PC/Mac/Linux (`agent.py` = MQTT loop, `runner.py` = ReAct + tools)
- LLM = OpenAI-compatible (default Typhoon, ตั้งใน `.env`)
- Tools: `os_exec` (shell), `web_search` (Serper), `query_kg` (RAM/disk/cwd)
- **โหมดทำงานตอนนี้ = "รับคำสั่งครั้งเดียว → ทำ → ตอบ"** (request/reply) ยังไม่มีงานยืนพื้น/automation

**MQTT topics ปัจจุบัน:**
| Topic | ทิศ | ใช้ |
|---|---|---|
| `{base}/hub/{name}/cmd` | app→hub | รับ NL task (MQTT5 ResponseTopic + CorrelationData) |
| `{base}/hub/{name}/cancel` | app→hub | ยกเลิก task |
| `{base}/hub/{name}/status` | hub→app | online (retained) / offline (LWT) |
| reply → ResponseTopic | hub→app | stream: `ping` / `chunk` / `end` |

**สิ่งที่ app ทำอยู่แล้ว (ฝั่งมือถือ):**
- `hub_control` ส่ง NL task ไป `/cmd` แบบเบื้องหลัง (detached) → เสร็จค่อย trigger กลับ (ระบบ A+B)
- app subscribe `{base}/#` และมี handler `{base}/alert` → เด้ง notification อยู่แล้ว ← **ช่องนี้ Hub ใช้แจ้งเตือน user ได้ทันที**

---

## 2. เป้าหมาย: Hub = automation brain (Agent-to-Agent)

```
┌─ มือถือ (SynaptaOS app) ───┐        ┌─ Hub (เปิดตลอด) ───────────────┐
│ agent แปลงภาษาคน → rule    │ ─set─► │ rule store (เก็บถาวร)          │
│ "พออุณหภูมิเกิน30 เปิดแอร์"  │        │ เฝ้า device state 24 ชม.        │
│ Rules screen (ดู/ลบ rule)  │ ◄list─ │ trigger จริง → ทำ action เอง:  │
│ รับ alert มาโชว์           │ ◄alert─│   • สั่งอุปกรณ์ (publish cmd)   │
└────────────────────────────┘        │   • os_exec บนเครื่อง           │
                                       │   • แจ้ง user (publish alert)   │
                                       └────────────────────────────────┘
```

**ทำไม Hub เหมาะ:** เปิดตลอด เชื่อถือได้ (มือถือโดน battery-kill), latency ต่ำ (local), offload มือถือ — เป็น pattern มาตรฐาน (Home Assistant / Node-RED)

**ขอบเขตหน้าที่:**
| งาน | อยู่ที่ |
|---|---|
| แปลงภาษาคน → rule spec | มือถือ (agent) |
| เก็บ rule + เฝ้า event + ทำ action บ้าน | **Hub** |
| แจ้งเตือน user | Hub → app (ผ่าน `alert` topic ที่ app รับอยู่แล้ว) |
| action บนมือถือ (เปิดแอป/ปลุก) | มือถือเท่านั้น (Hub สั่งไม่ได้ → route กลับ app, เฟสหลัง) |
| ad-hoc "เตือนฉันเมื่อ X" ชั่วคราว | มือถือ (`wait_event` ที่มีแล้ว) |

---

## 3. Protocol ที่จะเพิ่ม (app ↔ hub)

### Topics ใหม่
| Topic | ทิศ | payload |
|---|---|---|
| `{base}/hub/{name}/rules/set` | app→hub | rule JSON 1 ตัว (เพิ่ม/แก้) |
| `{base}/hub/{name}/rules/del` | app→hub | `{"id":"rule-..."}` |
| `{base}/hub/{name}/rules/list` | hub→app | array rule ปัจจุบัน (**retained** — app เปิดมาเห็นเลย) |
| `{base}/alert` | hub→app | ข้อความแจ้งเตือน (มี handler ใน app แล้ว) |

### Rule JSON spec (เสนอ)
```json
{
  "id": "rule-1717200000",
  "name": "ร้อนเปิดแอร์",
  "trigger": { "type": "sensor", "topic": "home/sensor/bedroom-temp", "op": ">", "value": 30 },
  "action": [
    { "type": "device", "topic": "home/ac/bedroom", "payload": "25" },
    { "type": "notify", "message": "อุณหภูมิเกิน 30° เปิดแอร์ให้แล้ว" }
  ],
  "cooldown_sec": 300,
  "enabled": true
}
```
- **trigger.type**: `sensor`/`device` (เทียบค่า state), เฟสหลัง: `time` (cron), `compound` (AND/OR หลายเงื่อนไข)
- **action.type**:
  - `device` → publish `{topic}/set` = payload (สั่งอุปกรณ์บ้านตรง ๆ)
  - `notify` → publish `{base}/alert` = message
  - `os_exec` หรือ `task` (NL) → ส่งเข้า `runner.run()` ของ Hub เอง (เปิดโปรแกรม/รันคำสั่ง)
  - (เฟสหลัง) `phone` → route กลับ app
- **cooldown_sec**: กันยิงรัว ๆ ตอนค่าแกว่งรอบ threshold

---

## 4. การออกแบบฝั่ง Hub

### 4.1 Trigger evaluation — แบบ deterministic เป็นหลัก (ไม่ใช้ LLM)
- Hub subscribe state topics (`{base}/+/+/state` หรือเจาะจงตาม rule)
- ทุก message → หา rule ที่ trigger.topic ตรง → เทียบ op/value → ถ้าจริง + พ้น cooldown → ยิง action
- **ทำไม deterministic:** เร็ว เชื่อถือได้ ถูก — automation ไม่ควรพึ่ง LLM ทุก tick

### 4.2 Action execution
- `device` → `client.publish("{base}/{topic}/set", payload)` (อุปกรณ์รับเอง)
- `notify` → `client.publish("{base}/alert", message)` → app เด้ง noti
- `task`/`os_exec` → เรียก `runner.run()` ที่มีอยู่ (Hub agent ลงมือทำ) ← จุดที่เป็น **Agent-to-Agent จริง**: rule เก็บ "งานภาษาคน" ไว้ พอ trigger ก็ให้ hub-agent คิดเอง

### 4.3 Rule store
- เก็บลงไฟล์ (`rules.json`) → โหลดตอนเปิด, republish `/rules/list` (retained)
- thread-safe (มี `_task_lock` pattern อยู่แล้ว)

### 4.4 ใช้ LLM แค่ตอนไหน
- **ไม่ใช้** ในการเฝ้า/เทียบ trigger (deterministic)
- **ใช้** เฉพาะ action แบบ NL (`task`) ที่ต้องตีความ → reuse runner.run
- (เฟสหลัง) ใช้ LLM ฝั่ง Hub แปลงภาษาคน→rule ก็ได้ ถ้าไม่อยากให้มือถือทำ — แต่ default ให้มือถือแปลง

---

## 5. แผนพัฒนาเป็นเฟส

| เฟส | ฝั่ง | งาน |
|---|---|---|
| **H1** | Hub | rule store (`rules.json`) + topics set/del/list (retained) |
| **H2** | Hub | trigger evaluation: subscribe state topics, เทียบ op/value, cooldown |
| **H3** | Hub | action: `device` (publish cmd) + `notify` (alert) |
| **H4** | Hub | action `task`/`os_exec` ผ่าน runner.run (Agent-to-Agent เต็มตัว) |
| **A1** | App | skill `create_rule` — agent แปลง "พอ...ให้..." → rule JSON → publish `/rules/set` |
| **A2** | App | Rules screen — subscribe `/rules/list` แสดง/ลบ rule |
| **A3** | App | route phone-action กลับมาทำบนมือถือ (rule ที่ action เป็น phone) |

> ตอนนี้ฝั่งมือถือ **คงไว้แค่ `wait_event` แบบเตือนเฉย ๆ** (เสถียรแล้วค่อยทำ A1–A3)

---

## 6. ข้อควรระวัง / คำถามเปิด
- **device topic ต้องตรงกัน** — rule อ้าง topic ของอุปกรณ์; ให้มือถือใส่ topic จริงจาก KG ลงใน rule (Hub ไม่ต้องเดา)
- **แหล่งความจริงของ rule = Hub** (retained `/rules/list`) — app แค่ display/ส่งคำสั่ง set/del
- **หลาย hub**: rule ผูกกับ `{name}` ของ hub ตัวที่จะทำ action นั้น
- **ความปลอดภัย**: rule สั่ง device/os_exec ได้ → ใช้ broker ที่เชื่อถือได้ + คง guard "ห้ามดำเนินการ" ใน system prompt เดิม
- **เวลา/cron trigger** (เฟสหลัง): Hub ต้องมี scheduler ของตัวเอง
- **เปลี่ยน LLM**: ปัจจุบัน Typhoon ผ่าน OpenAI-compatible; ถ้าจะใช้ gemma บน dgx เหมือน app ก็เปลี่ยน `.env` ได้ (base_url/model)

---

## 7. สรุปแนวคิดหลัก
Hub เปลี่ยนจาก *"รับคำสั่งครั้งเดียวแล้วทำ"* → *"รับ rule แล้วเฝ้า+ทำเองตลอด"* โดย:
- **มือถือ delegate งานยืนพื้นให้ hub** (Agent-to-Agent)
- เฝ้า/เทียบ = deterministic (เบา เชื่อถือได้) · ตีความภาษาคน = LLM เฉพาะที่จำเป็น
- แจ้ง user กลับผ่าน `alert` topic ที่ app รองรับอยู่แล้ว
- มือถือไม่อ้วนขึ้น (แค่เป็นรีโมตตั้ง rule + ตัวรับแจ้ง)
