# SynaptaHub — แผน Refactor MQTT → MCP (over Tailscale)

> เอกสารตั้งต้นก่อนลงมือ — สรุปการตัดสินใจ + ผลค้นข้อมูล + สถาปัตยกรรมเป้าหมาย
> เป้าหมาย: เปลี่ยน "หน้าบ้าน" ของ Hub (ช่องคุยกับ App) จาก MQTT → MCP ที่สื่อสารด้วย IP ผ่าน Tailscale
> วางรากฐานให้ **เพิ่มฟีเจอร์อะไรก็ได้ง่ายๆ** + โครงสร้างเป็นระเบียบ

---

## 1. สถาปัตยกรรมจริง (ความเข้าใจที่ถูกต้อง)

**LLM ไม่ได้อยู่ที่ Hub** — อยู่ที่ **DGX Spark** (gemma4:26b ผ่าน Ollama `:11434`) เข้าถึงผ่าน **Tailscale** (private mesh network). ทั้ง App และ Hub ต่าง "ยืม" สมองตัวนี้

```
                  ┌──────────────────────────────┐
                  │  DGX Spark  (Tailscale: dgx)  │
                  │  gemma4:26b @ Ollama :11434   │  ← สมองกลาง ใช้ร่วมกัน (มี vision)
                  └────▲──────────────────▲───────┘
        Tailscale     │                  │    Tailscale
                      │                  │
        ┌─────────────┴────┐     ┌───────┴─────────────────┐
        │  App (Flutter)   │     │  Hub (PC)               │
        │  • agent ตัวเอง  │     │  • agent ตัวเอง (ReAct) │
        │  • คุม IoT ตรง   │     │  • MCP server           │
        └──┬──────────▲────┘     └───────┬─────────────────┘
       MQTT│   MCP/IP │ (Tailscale)      │ MQTT (เฉพาะ automation
           │          └──────────────────┘  ที่ Hub สั่ง IoT เอง)
           ▼
   ┌───────────────┐
   │  MQTT Broker  │ ◄── Node (ESP32) เกาะผ่าน LAN (ลง Tailscale ไม่ได้)
   └───────────────┘
```

**บทบาท:**
- **App** = ผู้จัดการ — coordinate หลายระบบ (บ้าน + มือถือ + hub + ค้นเว็บ) ใช้สถาปัตยกรรม plan-and-execute
- **Hub** = ตัวเสริม — ทำสิ่งที่มือถือทำเดี่ยวๆ ไม่ได้ (รันคำสั่งบน PC, งานหนัก, เปิดตลอด 24 ชม., automation) มี agent ของตัวเอง (ReAct) ยืมสมอง gemma
- **Node** = อุปกรณ์ IoT จริง เกาะ MQTT

**หลักการชั้นความล้มเหลว:**
- Tailscale ล่ม → LLM ล่มทั้งระบบ (gemma อยู่ DGX ผ่าน Tailscale) → ความฉลาดดับ
- **แต่ควบคุม IoT แบบ manual ยังรอด** เพราะวิ่ง MQTT แยกขาดจาก Tailscale = มี fallback ชั้นล่าง

---

## 2. ขอบเขตการ refactor

เปลี่ยน **ช่องเดียว**: App ↔ Hub จาก MQTT (`hub/{name}/cmd` + ResponseTopic stream) → **MCP over Tailscale**

| ของเดิม | ทำอะไรกับมัน |
|---|---|
| MQTT loop หน้าบ้าน Hub (`agent.py` ทั้งไฟล์) | ❌ ตัดทิ้ง → แทนด้วย MCP server |
| MQTT ในระบบ (App↔Node) | ✅ เก็บไว้เหมือนเดิม |
| agent ของ Hub (`runner.py`) | ✅ เก็บ + เปลี่ยน LLM ไปชี้ DGX gemma |
| MQTT client | ➕ กลายเป็น "tool" ที่ agent หยิบใช้ตอน automation (ไม่ใช่ main loop) |

---

## 3. ผลค้นข้อมูล (เครื่องมือที่ยืนยันแล้ว)

| เรื่อง | ข้อสรุป | อ้างอิง |
|---|---|---|
| **Dart MCP client** | ใช้ `mcp_client` v2.0.0 — รองรับ streamable HTTP, sampling, elicitation, notification | [pub.dev/mcp_client](https://pub.dev/packages/mcp_client) |
| **Hub MCP server** | ใช้ **FastMCP** (official Python SDK) — pattern "1 ฟังก์ชัน = 1 tool" | — |
| **Streaming** | MCP streamable HTTP มี progress notification + spec พ.ย.2025 มี Tasks สำหรับงานยาว → แทน ping/chunk/end เดิมได้ | [MCP streaming](https://chatforest.com/guides/mcp-real-time-streaming/) |
| **Bidirectional** | MCP server→client ได้ผ่าน notification / sampling / elicitation → Hub push หา App ได้เอง | [MCP sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling) |
| **Tailscale บนมือถือ** | เป็น **VPN ของระบบ** (ฝัง library ในแอปไม่ได้) — VPN ติดแล้วแอปยิง HTTP ปกติ OS route ให้ | [tsnet (Go only)](https://tailscale.com/docs/features/tsnet) |
| **Tailscale Python** | `tsnet` เป็น Go เท่านั้น → Hub ใช้ Tailscale ของระบบ, bind `0.0.0.0` เข้าถึงผ่าน IP `100.x` | — |
| **mDNS ข้าม Tailscale** | **ไม่ได้** — Tailscale เป็น unicast mesh ไม่ส่ง multicast/broadcast | [FR #8884](https://github.com/tailscale/tailscale/issues/8884), [#11134](https://github.com/tailscale/tailscale/issues/11134) |
| **LLM gemma** | ยืนยันใช้ gemma DGX (ชนะ Typhoon เรื่อง args ภาษาไทย + offline + vision) | [dgx-notes](../dgx-notes-full-archive.md) |

---

## 4. โครงสร้าง code ใหม่ (Hub)

```
SynaptaOS-Hub/
  main.py            # จุดเริ่ม: สตาร์ท MCP server บน Tailscale IP + เปิด discovery/bridge
  config.py          # settings จาก .env รวมที่เดียว (DGX url, broker, port, token)
  server.py          # FastMCP — วนลงทะเบียน tools, รัน streamable-http
  agent.py           # agent ของ Hub (= runner.py เดิม) ReAct, ชี้ LLM ไป DGX gemma
  discovery.py       # อ่าน Tailscale IP → broadcast endpoint ผ่าน MQTT (ดูข้อ 6)
  tools/             # ◄── เมนู MCP — เพิ่มฟีเจอร์ = วางไฟล์ที่นี่
    __init__.py
    os_exec.py       # รันคำสั่งบนคอม (ของเดิม)
    web_search.py    # ค้นเว็บ (ของเดิม)
    system_info.py   # = kg.py เดิม (RAM/disk/cwd)
    iot.py           # publish MQTT สั่ง IoT (สำหรับ automation ของ Hub)
    task.py          # run_task → ส่งงานภาษาคนให้ agent.py คิดเอง (agent-to-agent)
```

**สูตรเพิ่มฟีเจอร์:** สร้าง `tools/<ชื่อ>.py` → เขียน `register(mcp)` ที่มี `@mcp.tool()` 1 ฟังก์ชัน → เติมชื่อใน list ที่ `server.py` 1 คำ → **App เห็น tool ใหม่เองผ่าน MCP** (ไม่ต้อง re-build แอป)

```python
# server.py
mcp = FastMCP("SynaptaHub")
from tools import os_exec, web_search, system_info, iot, task
for mod in (os_exec, web_search, system_info, iot, task):
    mod.register(mcp)
mcp.run(transport="streamable-http", host="0.0.0.0", port=8765)

# tools/iot.py — ตัวอย่าง
def register(mcp):
    @mcp.tool()
    def set_device(topic: str, value: str) -> str:
        """สั่งอุปกรณ์ IoT เช่น topic='bedroom/lamp', value='on'"""
        return mqtt_publish(f"{topic}/set", value)
```

**วินัย multi-user (เตรียมอนาคต แบบไม่ลงทุนตอนนี้):** agent ของ Hub ต้อง **stateless per-request** — ห้ามมี global/singleton state (ระวัง `os_exec._cwd` ที่เป็น global ปัจจุบัน) เพื่อให้วันหน้าห่อด้วย gateway คุม multi-user resource ได้ โดยไม่ต้องรื้อ engine ชั้นใน

---

## 5. Discovery & Pairing — Hub broadcast, App ยืนยัน

**หลักคิด:** อยู่ใน private network (Tailscale) เดียวกัน = เชื่อใจกันหมดแล้ว → **ไม่ต้องมี pairing code / fingerprint / token แลกกัน** (Tailscale ACL + WireGuard = ความปลอดภัยจบในตัว) ใช้ MQTT แค่ "broadcast ว่า Hub อยู่ไหน" หลังจากนั้นคุยผ่าน Tailscale ล้วน

**กลไก:** เติม IP:port ลงใน status ที่ Hub publish อยู่แล้ว

```
Hub เปิด → อ่าน Tailscale IP (tailscale ip -4) → publish (retained):
  {base}/hub/{name}/status  →  {"status":"online","host":"100.x.x.x","port":8765}

App (subscribe อยู่แล้ว) → เห็น online + host:port → เชื่อม MCP ตรงผ่าน Tailscale → ใช้งาน
```

- **broadcast** = retained message (ข้ามเน็ตได้ ต่างจาก mDNS) — App เปิดมาเห็นทันที
- **ยืนยัน** = App โชว์ Hub ที่เจอ ผู้ใช้แตะเลือก (ตัวเดียว auto) — ไม่มีพิธี
- **IP เปลี่ยน** = Hub republish → App อัปเดตเอง
- **หลาย Hub** = App subscribe `{base}/hub/+/status` เห็นทุกตัว
- **auto-discover เต็มรูป (อนาคต)** = เสริม Tailscale REST API `GET /api/v2/tailnet/-/devices` ได้ทีหลัง ([API](https://tailscale.com/kb/1101/api))

---

## 6. สถาปัตยกรรม Agent — 2 ชั้นที่ประกอบกัน

**ไม่ทำให้เหมือนกัน** — App กับ Hub ใช้คนละสถาปัตยกรรมเพราะแก้คนละปัญหา และมันซ้อนกันพอดี:

```
App (plan-and-execute) ──วางแผนระดับสูง, รันขนานข้าม subsystem──┐
   │ เจอ step ที่ต้องใช้ Hub → เรียก MCP run_task              │
   ▼                                                            │
Hub (ReAct) ──รับ sub-task เดียว, ใช้ tool belt ทำให้เสร็จ─────┘
```

| | ReAct (Hub) | Plan-and-Execute (App) |
|---|---|---|
| เก่ง | งานปลายเปิด ไม่รู้ step ล่วงหน้า (search→เห็น URL→เปิด) | หลาย step รู้ล่วงหน้า + รันขนาน + โชว์ plan |
| self-correct | มีในตัว (observation = error memory) | ต้องเติม reflect เอง |

**สรุป:** Hub คง ReAct ไว้ — เอา plan-execute มาใส่ = call เท่าเดิม/มากกว่า + โค้ดบาน. plan-execute จะคุ้มกับ Hub ก็ต่อเมื่อกลายเป็นสมอง automation รันหลาย action พร้อมกัน (ยังไม่ถึงจุดนั้น)

**Bidirectional (Dynamic 2 ทาง):** automation ฝั่ง Hub ทำงาน → Hub push notification ผ่าน MCP กลับหา App ได้เอง (ไม่ต้องรอ App ถาม)

---

## 7. Reflect — กู้คืนเมื่อ step ล้มเหลว (ฝั่ง App)

**ปัญหาเดิม** ([agent.dart:527](../synapta_mobile/lib/agent/agent.dart)): step พัง → เด้ง `response` ฟ้องผู้ใช้ทันที ไม่มีการลองแก้ — evaluator วิ่งเฉพาะตอนสำเร็จ

**ตำแหน่ง: ประตูคัดแยก หลัง executor ทันที (ไม่ใช่ท้ายสุด)**

```
router → executor → ┌─ REFLECT-GATE (หลัง executor) ─────────────────┐
                    │  1. ดักจับ error จาก r.failedSteps             │
                    │  2. recoverable? (เช็ค string — ฟรี ไม่ใช้ LLM) │
                    │     • แก้ได้ + retryCount<2 → evaluator (+บทเรียน)
                    │     • แก้ไม่ได้/เกินโควต้า   → response          │
                    └────────────────────────────────────────────────┘
         (สำเร็จ) → needsNextRound → evaluator | เสร็จ → response
```

**โค้ดที่เปลี่ยน (ทางแยกเดียว):**
```dart
if (r.hasFailedStep && _recoverable(r.failedSteps) && r.retryCount < 2) {
  r.retryCount++;
  r.reflections.add('รอบ ${r.routerRound}: ${step.type}(${param}) → ${reason}');
  r.evalNote = 'ขั้นก่อนล้มเหลว — วางแผนแก้ใหม่ ถ้าแก้ไม่ได้คืน steps ว่าง';
  node = 'evaluator';            // รีไซเคิล call เดิม ไม่มี node/prompt ใหม่
} else if (r.hasFailedStep) {
  node = 'response';             // แก้ไม่ได้ → ฟ้อง
} else if (r.needsNextRound && r.routerRound < 6) {
  node = 'evaluator';
} else {
  node = 'response';
}
```

**ประสิทธิภาพ + ค่าใช้จ่าย:**
- ตัวตัดสินใจ = `hasFailedStep` (check ธรรมดา ไม่ใช่ LLM) → **ระบบปกติเพิ่ม 0 call** จ่ายเฉพาะตอนพังจริง
- recoverable check จาก string (ฟรี): "ออฟไลน์/ติดต่อไม่ได้" = แก้ไม่ได้ ไม่เปลือง retry

**Error memory (กันทำซ้ำ):** `r.reflections` สะสมทุกรอบ → inject เข้า **ทั้ง router และ evaluator** prompt เป็น block `[เคยพยายามแล้วล้มเหลว — ห้ามทำซ้ำ]` กันกับดัก Reflexion ที่วนย้ำ error เดิม

**ปุ่มปรับค่าใช้จ่าย "แปลงเป็นคำพูด" (slot เดียวกัน):**
- **A. lean (เริ่มอันนี้):** error เราเป็นคำพูดอยู่แล้ว (`✗ ไม่พบ hub device...`) → ส่งดิบให้ evaluator วินิจฉัยในคอลเดียว — **+0 call**
- **B. rich (อัปทีหลัง):** ยิง LLM ในประตูเขียน "บทเรียน" จริงก่อนส่ง evaluator — **+1 call/พัง** (ทำเมื่อ evaluator วินิจฉัยไม่ไหว)

**ขอบเขต:** `retryCount < 2` + `routerRound < 6` ซ้อนกันกันลูป — เพดานคุณภาพ = evaluator วินิจฉัยเก่งแค่ไหน

> ฝั่ง Hub (ReAct) มี self-correct ในตัวอยู่แล้ว — reflect ที่ต้องเพิ่มจริงคือฝั่ง App ที่ pipeline มัน fixed

---

## 8. แผนเป็นเฟส

| เฟส | งาน |
|---|---|
| **H0** | โครงไฟล์ใหม่ + `config.py` + FastMCP เปล่า รัน streamable-http บน Tailscale IP ได้ + token guard |
| **H1** | ย้าย `os_exec` / `web_search` / `system_info` เป็น MCP tool |
| **H2** | `task.py` = `run_task` ห่อ agent เดิม + ปรับ `runner.py` ชี้ DGX gemma |
| **H3** | `discovery.py` — broadcast endpoint ผ่าน MQTT (retained status + IP) |
| **H4** | `iot.py` — tool ให้ agent Hub สั่ง IoT เอง (ฐานของ automation/rules) |
| **H5** | Hub→App push (notification) ตอน automation ทำงาน |
| **A1** | App: เปลี่ยน `hub_control` ([skills.dart:105](../synapta_mobile/lib/agent/skills.dart)) จาก MQTT → `mcp_client` ผ่าน Tailscale |
| **A2** | App: หน้าจอ "พบ Hub" จาก discovery + เก็บ endpoint |
| **A3** | App: เพิ่ม REFLECT-GATE + error memory ใน loop (ข้อ 7) |
| **A4** | (ต่อยอด) App ดึงรายการ tool จาก Hub แบบไดนามิก แทน hardcode skill |

H0–H3 = รากฐานใช้งานได้จริง · H4+ และ A4 = ต่อยอด

---

## 8.5 อัปเดตสถาปัตยกรรม (2026-06-04) — pairing + per-user storage + multi-hub

หลังทำ H0–H5 / A1–A3 เสร็จ ปรับดีไซน์ให้รองรับ production หลาย Hub + multi-user:

- **รหัสย้ายไปตอนจับคู่ (ไม่อยู่หน้าตั้งค่า):** Hub broadcast แค่ ชื่อ+IP+port ผ่าน MQTT. App เห็น Hub ใหม่ → กดจับคู่ → กรอกรหัส → `register(user_id, app_name)` ผ่าน Tailscale (รหัสผิด = guard ตอบ 401). สำเร็จแล้ว Hub จดแอป, App เก็บ endpoint+token+tools ราย Hub
- **ต่อได้หลาย Hub:** App เก็บ paired hubs เป็น list (`HubController`). ทุกครั้งที่ต่อ/กลับมาออนไลน์ → ดึง `tools/list` มาอัปเดต (= A4 ทำแล้ว)
- **agent เลือก Hub (`hub_agent.pickHub`):** ดู tool ของทุก Hub ที่จับคู่ → ตัดสินว่าคำสั่ง user ส่งไป Hub ไหน สั่งอะไร
- **เก็บข้อมูลฝั่ง Hub แบบเป็นระเบียบ แยกไฟล์ แยก user (รองรับ multi-user):**
  ```
  data/registry.json
  data/users/<user_id>/{profile,kd,scenes,routines,phone}.json
  ```
  agent อ่านเฉพาะไฟล์ที่ต้องใช้ (`get_user_data`/`load_part`) — ไม่เปลือง context. App `sync_data` ส่งเฉพาะส่วนที่เปลี่ยน (debounce), full sync ตอนจับคู่
- **Python พกพา:** `osprofile.py` แยกคำสั่งตาม OS (windows/linux/mac, unknown→linux) — production ชุดแรกรันบน **Raspberry Pi 5**

### TODO อนาคต — ตั้งค่า Hub ผ่าน GUI บน web app
ต่อไป Hub จะมี **หน้าเว็บ (web app GUI)** สำหรับตั้งค่าระบบ:
- คุยกับ **agent ของระบบโดยตรงผ่านเว็บ** (ไม่ต้องผ่านมือถือ)
- **อ่าน + แก้ไขข้อมูล** (registry, ข้อมูลแต่ละ user: kd/scenes/routines/phone/profile) ได้จากหน้าเว็บนั้นเลย
- เหมาะกับตอนตั้ง Hub ครั้งแรกบน RPi / ดูแลหลาย user — โครง store.py แยกไฟล์ต่อ user รองรับอยู่แล้ว

---

## 9. ข้อกำหนดการสื่อสาร (สรุป)

- App↔Hub = HTTPS/MCP ผ่าน Tailscale IP เท่านั้น (ไม่เปิด public)
- Auth: Tailscale ACL (ใครเข้าวงได้) เป็นด่านหลัก + token ง่ายๆ ใน MCP header กันแอปแปลกในวง
- MQTT (App↔Node + Hub broadcast) แยกขาด ไม่พึ่ง Tailscale
- LLM: ทั้ง App และ Hub agent ชี้ `http://dgx:11434/v1`, model `gemma4:26b`

---

## Sources
[mcp_client](https://pub.dev/packages/mcp_client) · [MCP sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling) · [MCP streaming](https://chatforest.com/guides/mcp-real-time-streaming/) · [Tailscale API](https://tailscale.com/kb/1101/api) · [Tailscale OAuth](https://tailscale.com/kb/1215/oauth-clients) · [tsnet](https://tailscale.com/docs/features/tsnet) · [Tailscale multicast FR #8884](https://github.com/tailscale/tailscale/issues/8884) · [Reflexion framework](https://woliveiras.com/posts/introduction-to-the-reflexion-framework/)
