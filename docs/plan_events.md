# SynaptaOS Hub — Event-driven Agent System

เป้าหมาย: ทำให้ Hub "ตอบสนองเหตุการณ์เองได้" (เซ็นเซอร์/เวลา/อุปกรณ์ออฟไลน์/ตำแหน่ง)
ไม่ใช่แค่รอรับคำสั่ง — และยกระดับ "สมอง" เป็น agent harness เต็มรูปแบบ

---

## หลักการสำคัญ: แยก 2 ชั้น — LLM เป็นทางเลือกสุดท้าย

ห้ามเอา LLM ไปผูกกับทุก event ตรง ๆ (เซ็นเซอร์ยิงทุกวิ = ปลุก gemma ทุกวิ → DGX ละลาย)

```
┌─ ชั้น A: ระบบประสาท (event layer) — เร็ว ถูก ไม่มี LLM ──────────┐
│  sources → bus → rule engine → ทำเลย (deterministic)            │
│                              └→ escalate ขึ้นชั้น B (เมื่อต้องคิด)  │
└────────────────────────────────────────────────────────────────┘
┌─ ชั้น B: สมอง (agent brain) — ช้า แพง มี LLM ───────────────────┐
│  pipeline pool → LlamaIndex Workflow (plan/tool/reflect/verify)  │
└────────────────────────────────────────────────────────────────┘
```

กฎทอง: event ส่วนใหญ่จบที่ชั้น A ด้วย rule ธรรมดา จะขึ้นชั้น B เฉพาะตอนต้องตัดสินใจ/เรียบเรียงจริง

---

## ชั้น A — Event layer

### Event (events/event.py)
หน่วยเหตุการณ์รูปเดียวกันจากทุกแหล่ง:
- `type`  — "device" | "schedule" | "device_offline" | "phone" | "geofence"
- `key`   — ตัวระบุในชนิดนั้น (เช่น topic อุปกรณ์)
- `value` — ค่าใหม่
- `user_id`, `ts`, `meta`

### Bus (events/bus.py)
pub/sub ในเครื่องเบา ๆ — source เรียก `publish(ev)`, engine เรียก `subscribe(fn)`
handler รันใน thread ของผู้ส่ง → ต้องเร็ว ห้ามบล็อก (งานหนักโยนเข้า pipeline)

### Event sources
| source | สถานะ | จุดต่อ |
|---|---|---|
| device/sensor (MQTT) | ✅ Phase 1 | tap ที่ `device_state.on_message` |
| schedule (เวลา) | มี automation.py อยู่แล้ว | Phase 4 ค่อยรวมเป็น rule trigger |
| device_offline (watchdog) | Phase 4 | เช็ค ts ล่าสุดของ devstate |
| phone (แบต/geofence) | Phase 4 | จาก telemetry ที่แอป publish |

### Rule engine (events/rules.py) — declarative + escalate
กฎเก็บไฟล์ `data/event_rules.json` (เหมือน hub_jobs.json)

โครงกฎ:
```json
{
  "id": "rule-...", "user_id": "...", "name": "...", "enabled": true,
  "trigger": {"type": "device", "topic": "bedroom/temp", "op": ">", "value": "30"},
  "action": {"kind": "device", "topic": "bedroom/ac", "value": "ON"},
  "cooldown_sec": 300, "once": false
}
```

`trigger.op`: `>` `<` `>=` `<=` `==` `!=` (เทียบค่า) | `change` (เปลี่ยนค่าใด ๆ)

`action.kind`:
- `device` → `publish_set(topic, value)` — สั่งอุปกรณ์ (ไม่ใช้ LLM)
- `notify` → `account.send_app_command(uid, text, "chat", wait=False)` — เด้งแจ้งเจ้าของ (ไม่ใช้ LLM)
- `agent`  → `pipeline.submit(AgentTask(task=...))` — **escalate ขึ้นสมอง** (ใช้ LLM) แล้วรายงานผลกลับเจ้าของ

พฤติกรรมสำคัญ:
- **edge-trigger** — กฎเทียบค่า "ยิงครั้งเดียวตอนข้ามเส้น" (31→32→33 ที่ >30 ยิงหนเดียว) กลับมายิงใหม่เมื่อค่าตกใต้เส้นแล้วข้ามขึ้นอีก
- **cooldown** — กันยิงรัวภายใน N วิ
- **once** — ทำครั้งเดียวแล้วปิดกฎ

MCP tools (ให้ App/agent สร้างกฎได้): `add_rule`, `list_rules`, `remove_rule`

> หมายเหตุ: `wait_event`/routines ฝั่ง App ควรย้ายมาเป็น rule บน Hub (Phase 2) เพราะมือถือหลับ/ออฟไลน์ได้ เฝ้า event 24 ชม. ไม่ได้ — Hub เปิดตลอด

---

## ชั้น B — Agent brain (LlamaIndex Workflows)

แทน `create_react_agent` ตัวเดียว → Workflow แบบ event-driven (step ฟัง event ยิง event ใหม่)

```
StartEvent(task) → PlanEvent → ToolCallEvent → ToolResultEvent
   ToolResultEvent ─ พลาด? → ReflectEvent (วิเคราะห์+จดกัน, retry เพดาน) → PlanEvent
                   └ สำเร็จ → VerifyEvent (สั่ง iot/system แล้วอ่านสถานะกลับมาเทียบ) → StopEvent(reply)
```

- LLM: `OpenAILike` ชี้ base_url ไป Ollama@DGX (เหมือน ChatOpenAI เดิม)
- tools: ห่อเป็น `FunctionTool` (ของเดิมใน agent.py ยกมาได้)
- Context: ถือ messages, reflections (error memory), retry_count
- reflect/verify: ยกตรรกะจากฝั่ง App (`_recoverable` + reflections) มาใส่
- supervisor + sub-agent แยกทีม (system/web/user/iot) → เปิดใช้ `tool_group()` ที่เตรียมไว้ → gemma เลือก tool ถูกขึ้น
- guardrail: คั่นก่อนรัน `system_exec` อันตราย → ขออนุมัติก่อนทำจริง
- ของรอบนอกไม่ต้องแตะ: pipeline pool, automation, A2A, MCP server เก็บไว้เหมือนเดิม — เปลี่ยนแค่ข้างใน `agent.run()`

dependencies เพิ่ม: `llama-index-core`, `llama-index-llms-openai-like`

---

## แผนทำเป็นเฟส — สถานะปัจจุบัน

1. **Phase 1 ✅** — event layer: bus + Event + engine (edge + cooldown + once) + tap device_state + MCP CRUD
2. **Phase 2 ✅** — rule engine ฝั่ง Hub เก่งขึ้น: หลายเงื่อนไข AND/OR + แหล่งพิเศษ (`__time__`/`__weekday__`/`__battery__`/`__charging__`/`online:`) + action `scene` + escalation `agent`
   - **ตัดสินใจ: ไม่ย้าย routine จาก App** (กันยิงซ้ำ/ไม่แตะ App) → Hub มี rule ของตัวเองสำหรับ automation ที่สร้างบน Hub
3. **Phase 3 ✅ (ทดสอบบน DGX จริงผ่าน)** — สมอง LlamaIndex Workflow (`brain/`) + reflect + streaming · **ดีฟอลต์ `config.BRAIN=workflow`** (ตั้ง `BRAIN=react` เพื่อย้อนกลับ) · ทั้ง agent.run และ agent.astream_run route เข้า workflow → web admin/App ใช้สมองเดียวกันหมด
4. **Phase 4 ✅ (บางส่วน)** — offline ทำผ่าน value source `online:` + engine tick (ไม่ต้องมี watchdog แยก) · telemetry tap ป้อนแบต/ชาร์จเข้า engine
   - **เหลือ:** geofence, supervisor/sub-agent (tool scoping), guardrail ก่อนรัน system_exec, verify หลังสั่ง, persistence/checkpointer ของสมอง

### โครงไฟล์ที่ลงจริง
- ชั้น A: `src/events/` — event.py, bus.py, values.py, actions.py, engine.py, rules.py
- ชั้น B: `src/brain/` — __init__.py (facade run), tools.py (FunctionTool), workflow.py (HubBrain + reflect)
- tap: `device_state.on_message` (device) + `telemetry.on_message` (phone) → `events.publish`
- routing: `agent.run` เช็ค `config.BRAIN` → react (LangGraph) หรือ workflow (LlamaIndex), session แก้ที่เดียว
- เปิดใช้สมองใหม่: ตั้ง env `BRAIN=workflow` แล้วรันบน Hub ที่ต่อ DGX ได้ → ลองสั่งงานที่ต้องใช้ tool
