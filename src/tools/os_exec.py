"""
OS command execution tool.

Stateless per-request: ไม่มี global cwd แล้ว — cwd เก็บใน "cwd_box" (dict) ที่ผู้เรียก
สร้างใหม่ทุกครั้ง. ภายใน task เดียว agent ส่ง box เดิมเข้ามา → cd ค้างได้ในงานนั้น
แต่ไม่รั่วข้าม request (พร้อมรองรับ multi-user วันหน้าโดยไม่ต้องรื้อ)
"""

import subprocess
import threading
from pathlib import Path

_BASE = str(Path(__file__).resolve().parent.parent)
_proc: subprocess.Popen | None = None
_proc_lock = threading.Lock()


def run(
    command: str,
    timeout: float = 60,
    kill_event: threading.Event | None = None,
    cwd_box: dict | None = None,
) -> str:
    global _proc

    if cwd_box is None:
        cwd_box = {"cwd": _BASE}      # call เดี่ยว — cwd ใช้ครั้งเดียว ไม่ค้าง
    cwd = cwd_box.get("cwd", _BASE)

    cmd = command.strip()

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
    try:
        with _proc_lock:
            _proc = subprocess.Popen(
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
        for line in _proc.stdout:
            if kill_event and kill_event.is_set():
                break
            lines.append(line.rstrip())

        if kill_event and kill_event.is_set():
            _proc.kill()
            return "[cancelled]"

        try:
            _proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _proc.kill()
            lines.append(f"[timeout after {timeout:.0f}s]")
            exit_status = "timeout"

        if _proc.returncode and exit_status == "ok":
            exit_status = "error"

        return "\n".join(lines) or "(no output)"

    except Exception as e:
        return f"[error] {e}"

    finally:
        with _proc_lock:
            _proc = None


def cancel() -> None:
    with _proc_lock:
        p = _proc
    if p:
        p.kill()


# ── MCP tool ─────────────────────────────────────────────────────────────────
def register(mcp):
    import config

    @mcp.tool()
    def os_exec(command: str) -> str:
        """รันคำสั่ง terminal บนเครื่องนี้ (Windows/mac/linux) แล้วคืน output. คำสั่งเดียวจบในตัว ไม่ค้าง directory ข้ามครั้ง"""
        return run(command, timeout=config.COMMAND_TIMEOUT)
