"""
osprofile — คำสั่งตัวอย่างต่อระบบปฏิบัติการ (แยกออกมาให้สลับ OS ได้ง่าย)

Hub ชุดแรกของ production จะรันบน Raspberry Pi 5 (Linux/ARM) แต่ตอน dev อยู่บน Windows
→ เก็บคำสั่งเฉพาะ OS ไว้ที่เดียว เพิ่ม OS ใหม่ = เติม dict ก้อนเดียว ไม่ต้องแก้ agent
"""

# แต่ละ OS: คำสั่งจริงสำหรับงานที่พบบ่อย + บล็อกตัวอย่างที่ยัดเข้า system prompt ของ agent
_PROFILES = {
    "windows": {
        "open_url": "start <url>",
        "disk": "wmic logicaldisk get size,freespace",
        "shutdown": "shutdown /s /t 0",
        "examples": '''- "เปิด YouTube" → os_exec("start https://youtube.com")
- "เปิดเพลง X" → ✅ ค้นก่อนเสมอ: web_search("X เพลง YouTube") → เอา URL "จริง" ที่ได้ → os_exec("start <url>")   (❌ ห้ามมั่ว/เดา URL เองโดยไม่ค้น)
- "ดู disk ที่เหลือ" → os_exec("wmic logicaldisk get size,freespace")
- "shutdown" → os_exec("shutdown /s /t 0")
- "pause/เล่นเพลง" → os_exec('powershell -c "(New-Object -com WScript.Shell).SendKeys([char]179)"')
- "เพิ่มเสียง" → os_exec('powershell -c "(New-Object -com WScript.Shell).SendKeys([char]175)"')''',
    },
    "linux": {  # ใช้กับ Raspberry Pi 5 (Debian/ARM) ด้วย
        "open_url": "xdg-open <url>",
        "disk": "df -h",
        "shutdown": "shutdown -h now",
        "examples": '''- "เปิด YouTube" → os_exec("xdg-open https://youtube.com")
- "เปิดเพลง X" → ✅ ค้นก่อนเสมอ: web_search("X เพลง YouTube") → เอา URL "จริง" ที่ได้ → os_exec("xdg-open <url>")   (❌ ห้ามมั่ว/เดา URL เองโดยไม่ค้น)
- "ดู disk ที่เหลือ" → os_exec("df -h")
- "shutdown" → os_exec("shutdown -h now")   # บางเครื่องต้อง sudo
- "pause/เล่นเพลง" → os_exec("playerctl play-pause")
- "เพิ่มเสียง" → os_exec("amixer set Master 5%+")''',
    },
    "mac": {
        "open_url": "open <url>",
        "disk": "df -h",
        "shutdown": "shutdown -h now",
        "examples": '''- "เปิด YouTube" → os_exec("open https://youtube.com")
- "เปิดเพลง X" → ✅ ค้นก่อนเสมอ: web_search("X เพลง YouTube") → เอา URL "จริง" ที่ได้ → os_exec("open <url>")   (❌ ห้ามมั่ว/เดา URL เองโดยไม่ค้น)
- "ดู disk ที่เหลือ" → os_exec("df -h")
- "shutdown" → os_exec("sudo shutdown -h now")
- "pause/เล่นเพลง" → os_exec("osascript -e 'tell application \\"Music\\" to playpause'")
- "เพิ่มเสียง" → os_exec("osascript -e 'set volume output volume (output volume of (get volume settings) + 10)'")''',
    },
}


def profile(os_type: str) -> dict:
    """คืน command profile ของ OS — ไม่รู้จักก็ตกมาที่ linux (ปลอดภัยสุดสำหรับ RPi/server)"""
    return _PROFILES.get(os_type, _PROFILES["linux"])


def os_block(os_type: str) -> str:
    """คืน 'บล็อก prompt เฉพาะ OS' ทั้งก้อน (ส่วนของ system prompt ที่ต่างกันตาม OS)

    ดึงมาเฉพาะ OS ปัจจุบันเท่านั้น — ไม่ยัดทั้ง 3 OS เข้า prompt = ประหยัด context
    อยากเพิ่ม guidance เฉพาะ OS (กฎ/ข้อควรระวัง/path) → เติมในก้อนนี้ที่เดียว ไม่ต้องแตะ agent.py
    """
    p = profile(os_type)
    return f"[ตัวอย่างวิธีทำงาน บนเครื่อง {os_type}]\n{p['examples']}"
