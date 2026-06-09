"""
actions — ลงมือทำเมื่อกฎเข้าเงื่อนไข (4 แบบ)

  device → สั่งอุปกรณ์ 1 ตัว (publish_set)              ─┐ ทำเลย ไม่ใช้ LLM
  scene  → สั่งทั้งชุดตาม "สภาพแวดล้อม" ที่ตั้งไว้        ─┤
  notify → เด้งข้อความเข้าแอปเจ้าของ (FCM)               ─┘
  agent  → โยนงานให้สมอง (pipeline) คิด+ทำ+รายงานกลับ    ← escalate ใช้ LLM

payload อุปกรณ์ digital ส่ง "true"/"false", analog ส่งตัวเลข — ให้ตรงกับที่แอปส่งไป Node
"""
import logging

import config

_log = logging.getLogger("events.actions")


def run(action: dict, user_id: str | None) -> str:
    kind = action.get("kind")
    if kind == "device":
        from tools.iot import publish_set
        return publish_set(action["topic"], str(action["value"]))
    if kind == "scene":
        return _run_scene(action.get("scene_id", ""), user_id)
    if kind == "notify":
        if user_id:
            from tools import account
            account.send_app_command(user_id, action.get("text", ""), "chat",
                                     sender=config.AGENT_NAME, wait=False)
        return f"notify → {user_id or '(ไม่มีเจ้าของ)'}"
    if kind == "agent":
        return _escalate(action.get("task", ""), user_id)
    return f"action kind ไม่รู้จัก: {kind}"


def _escalate(task: str, user_id: str | None) -> str:
    """โยนงานเข้า pipeline pool → สมองทำ แล้วรายงานผลกลับเจ้าของผ่าน FCM"""
    import pipeline
    from pipeline.task import AgentTask

    def report(result: str) -> None:
        if user_id:
            from tools import account
            account.send_app_command(user_id, result, "chat",
                                     sender=config.AGENT_NAME, wait=False)

    ok = pipeline.submit(AgentTask(task=task, user_id=user_id or None, source="rule",
                                   history=[], reply=report), block=False)
    return "เข้า pool แล้ว" if ok else "pool คิวเต็ม ข้าม"


def _run_scene(scene_id: str, user_id: str | None) -> str:
    """รัน scene: หาอุปกรณ์ตาม deviceId ใน kd → แปลงค่า → สั่งทีละตัว · มี prompt ก็ส่งให้สมองทำต่อ"""
    if not user_id:
        return "scene: ไม่มีเจ้าของ"
    import store
    from tools.iot import publish_set

    scenes = store.load_part(user_id, "scenes") or []
    scene = next((s for s in scenes if s.get("id") == scene_id), None)
    if not scene:
        return f"scene: ไม่พบ {scene_id}"

    by_id = {d.get("id"): d for d in (store.load_part(user_id, "kd") or [])}
    done = []
    for a in scene.get("actions", []):
        d = by_id.get(a.get("deviceId"))
        if not d or not d.get("topic"):
            continue
        val = a.get("value")
        if d.get("type") == "digital":
            payload = "true" if (val is True or str(val).lower() in ("true", "1", "on")) else "false"
        else:
            payload = str(int(val)) if isinstance(val, (int, float)) else str(val)
        publish_set(d["topic"], payload)
        done.append(d.get("name", d["topic"]))

    # scene มีคำสั่งเสริมเป็นข้อความ (เช่น "เปิดเพลงผ่อนคลาย") → ฝากให้สมองทำต่อ
    prompt = (scene.get("prompt") or "").strip()
    if prompt:
        _escalate(prompt, user_id)

    return f"scene «{scene.get('name', scene_id)}»: {', '.join(done) if done else 'ไม่มีอุปกรณ์'}" \
           + (" (+คำสั่งเสริม)" if prompt else "")
