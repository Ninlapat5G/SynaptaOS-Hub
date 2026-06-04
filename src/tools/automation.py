"""
automation (H5) — Hub push notification กลับหา App ผ่าน MCP

เมื่อ automation ทำงาน (เงื่อนไขถึง → สั่ง IoT) Hub ส่ง notification กลับ App เอง
ผ่าน MCP session (server→client) ไม่ต้องรอ App ถาม — นี่คือช่อง bidirectional

โครงสาธิต: รับ rule → ทำ action → push ผลกลับ
automation engine เต็ม (เงื่อนไข/ตารางเวลา) ต่อยอดทีหลัง บนช่อง push เดียวกันนี้
"""

from mcp.server.fastmcp import Context

from tools import iot


def register(mcp):
    @mcp.tool()
    async def run_automation(name: str, device_topic: str, value: str, ctx: Context) -> str:
        """รัน automation: สั่ง IoT แล้ว push แจ้งเตือนกลับหา App ระหว่างทำงาน เช่น name='ไฟห้องนอน', device_topic='bedroom/lamp', value='on'"""
        await ctx.info(f"[automation:{name}] กำลังสั่ง {device_topic} = {value}")
        result = iot.publish_set(device_topic, value)
        await ctx.info(f"[automation:{name}] เสร็จ: {result}")
        return result
