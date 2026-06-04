#!/usr/bin/env bash
# ── SynaptaOS Hub launcher (Linux / Raspberry Pi) ────────────────────────────
# ครั้งแรก: สร้าง venv + ลง requirements ให้อัตโนมัติ · ครั้งต่อไป: รันเลย
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[setup] ยังไม่มี venv - สร้างครั้งแรก..."
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

echo "[run] เริ่ม SynaptaOS Hub..."
exec .venv/bin/python src/main.py
