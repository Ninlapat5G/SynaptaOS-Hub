"""
System info (เดิมคือ kg.py)
===========================
สถานะเครื่อง: OS, CPU, RAM, disk + helper วันเวลาไทย

ตัด Session/cwd ออก (os_exec stateless แล้ว ไม่มี global cwd) — รายงาน base dir แทน
"""

from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psutil

_BKK = ZoneInfo('Asia/Bangkok')
_THAI_DAYS = ['วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี',
              'วันศุกร์', 'วันเสาร์', 'วันอาทิตย์']
_THAI_MONTHS = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน',
                'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
                'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']


def now_thai() -> str:
    """คืนเวลาแบบไทย เช่น 'วันศุกร์ที่ 9 พฤษภาคม ค.ศ. 2026 เวลา 14:23 น. (GMT+7)'"""
    n = datetime.now(_BKK)
    return (
        f'{_THAI_DAYS[n.weekday()]}ที่ {n.day} {_THAI_MONTHS[n.month]} '
        f'ค.ศ. {n.year} เวลา {n.hour:02d}:{n.minute:02d} น. (GMT+7)'
    )


_HOSTNAME = platform.node()
_OS_FULL  = f"{platform.system()} {platform.release()} ({platform.version()})"
_CPU      = platform.processor() or 'unknown'
_CORES    = psutil.cpu_count(logical=False) or 1
_CPU_FREQ = psutil.cpu_freq()
_FREQ_STR = f" @ {_CPU_FREQ.max / 1000:.1f} GHz" if _CPU_FREQ else ""
_BASE     = str(Path(__file__).resolve().parent.parent)


def _live_resources() -> dict[str, Any]:
    mem  = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {
        'ram_total_gb':  mem.total // (1024**3),
        'ram_free_gb':   mem.available // (1024**3),
        'disk_total_gb': disk.total // (1024**3),
        'disk_free_gb':  disk.free // (1024**3),
        'cpu_percent':   psutil.cpu_percent(interval=None),
    }


def snapshot_text() -> str:
    res = _live_resources()
    try:
        from discovery import tailscale_ip
        import config
        ip = tailscale_ip()
        admin_url = f"http://{ip}:{config.MCP_PORT}/admin"
    except Exception:
        admin_url = "unknown"
        
    lines = [
        '[SYSTEM INFO — สถานะเครื่อง]',
        '',
        'Machine:',
        f'  ├─ hostname: {_HOSTNAME}',
        f'  ├─ os:       {_OS_FULL}',
        f'  ├─ cpu:      {_CPU} — {_CORES} cores{_FREQ_STR}  ({res["cpu_percent"]:.0f}% busy)',
        f'  ├─ ram:      {res["ram_free_gb"]} GB free / {res["ram_total_gb"]} GB total',
        f'  ├─ disk:     {res["disk_free_gb"]} GB free / {res["disk_total_gb"]} GB total',
        f'  └─ admin_url: {admin_url}',
        '',
        f'Base dir: {_BASE}',
    ]
    return '\n'.join(lines)


# ── MCP tool ─────────────────────────────────────────────────────────────────
def register(mcp):
    @mcp.tool()
    def system_info() -> str:
        """ดูสถานะเครื่อง Hub ปัจจุบัน: OS, CPU, RAM ว่าง, disk ว่าง"""
        return snapshot_text()
