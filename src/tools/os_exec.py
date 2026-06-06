"""
OS command execution tool.

Stateless per-request: ไม่มี global cwd แล้ว — cwd เก็บใน "cwd_box" (dict) ที่ผู้เรียก
สร้างใหม่ทุกครั้ง. ภายใน task เดียว agent ส่ง box เดิมเข้ามา → cd ค้างได้ในงานนั้น
แต่ไม่รั่วข้าม request (พร้อมรองรับ multi-user วันหน้าโดยไม่ต้องรื้อ)
"""

import re
import subprocess
import threading
from pathlib import Path

_BASE = str(Path(__file__).resolve().parent.parent)

# ── ด่านความปลอดภัยระดับโค้ด (ไม่ขึ้นกับว่า LLM คิดยังไง) ─────────────────────
# คำสั่งทำลายล้าง — บล็อกเสมอ ไม่ว่าใครสั่ง
_DANGER = [
    r"\brm\s+-rf?\s+(/|~|\*|\$home)",   # ลบทั้ง root/home
    r"\bmkfs\b", r"\bformat\b", r"\bdiskpart\b",
    r"\bdd\s+if=", r">\s*/dev/sd",
    r"\bdel\s+/[sq]", r"\brmdir\s+/s", r"\brd\s+/s",
    r":\(\)\s*\{.*\}\s*;",               # fork bomb
    r"\bremove-item\b.*-recurse.*-force",
]
# คำสั่งปิด/รีสตาร์ทเครื่อง — รันได้เฉพาะเมื่อมาจากผู้ใช้จริง (ผ่าน App/หน้าเว็บ) เท่านั้น
_POWER = [
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b", r"\bhalt\b",
    r"\binit\s+[06]\b", r"\bstop-computer\b", r"\brestart-computer\b",
]


def _blocked(cmd: str, allow_power: bool) -> str | None:
    """คืนข้อความปฏิเสธถ้าคำสั่งต้องห้าม — ไม่ต้องห้ามคืน None"""
    low = cmd.lower()
    for pat in _DANGER:
        if re.search(pat, low):
            return "[blocked] คำสั่งนี้อันตรายเกินไป ไม่อนุญาตให้รันค่ะ"
    if not allow_power:
        for pat in _POWER:
            if re.search(pat, low):
                return "[blocked] การปิด/รีสตาร์ทเครื่องต้องสั่งจากผู้ใช้ผ่านแอปเท่านั้นค่ะ"
    return None


def run(
    command: str,
    timeout: float = 60,
    kill_event: threading.Event | None = None,
    cwd_box: dict | None = None,
    allow_power: bool = False,
) -> str:
    if cwd_box is None:
        cwd_box = {"cwd": _BASE}      # call เดี่ยว — cwd ใช้ครั้งเดียว ไม่ค้าง
    cwd = cwd_box.get("cwd", _BASE)

    cmd = command.strip()

    refusal = _blocked(cmd, allow_power)
    if refusal:
        return refusal

    # cd จัดการแยก — subprocess ไม่ persist การเปลี่ยน directory
    if cmd.lower() == "cd" or cmd.lower().startswith("cd "):
        target = cmd[2:].strip().strip('"').strip("'")
        if not target or target == "~":
            new_path = Path.home()
        elif target == "..":
            new_path = Path(cwd).parent
        else:
            new_path = (Path(cwd) / target).resolve()

        if new_path.is_dir():
            cwd_box["cwd"] = str(new_path)
            return f"[cwd] {new_path}"
        return f"[error] Directory not found: {target}"

    exit_status = "ok"
    proc = None        # local ต่อ call — ไม่ใช้ global แล้ว (หลาย user รันพร้อมกันไม่ชนกัน)
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        lines: list[str] = []
        for line in proc.stdout:
            if kill_event and kill_event.is_set():
                break
            lines.append(line.rstrip())

        if kill_event and kill_event.is_set():
            proc.kill()
            return "[cancelled]"

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            lines.append(f"[timeout after {timeout:.0f}s]")
            exit_status = "timeout"

        if proc.returncode and exit_status == "ok":
            exit_status = "error"

        return "\n".join(lines) or "(no output)"

    except Exception as e:
        return f"[error] {e}"


# ── MCP tool ─────────────────────────────────────────────────────────────────
def register(mcp):
    import config

    @mcp.tool()
    def os_exec(command: str) -> str:
        """รันคำสั่ง terminal บนเครื่องนี้ (Windows/mac/linux) แล้วคืน output. คำสั่งเดียวจบในตัว ไม่ค้าง directory ข้ามครั้ง"""
        return run(command, timeout=config.COMMAND_TIMEOUT)
