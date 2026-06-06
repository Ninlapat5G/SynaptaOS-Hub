"""
run_task — ส่งงานภาษาคนให้ agent ของ Hub คิด/ทำเอง (agent-to-agent)

App (plan-and-execute) เจอ step ที่ต้องให้ Hub ทำ → เรียก run_task →
Hub agent (ReAct) รับ sub-task เดียว ใช้ tool belt ทำจนเสร็จ แล้วคืนผลกลับ
"""


def register(mcp):
    import asyncio
    import agent

    @mcp.tool()
    async def run_task(task: str, user_id: str = "") -> str:
        """ส่งงานภาษาธรรมชาติให้ Hub ทำบนเครื่องนี้ เช่น 'เปิดเพลง lofi', 'ดู disk ที่เหลือ', 'shutdown'. Hub คิดเองว่าใช้คำสั่งอะไรแล้วลงมือทำ. user_id = รหัสแอปที่ลงทะเบียน (ให้ Hub ดึงข้อมูลของผู้ใช้คนนั้นมาใช้ได้)"""
        # โยน agent.run (sync + อาจบล็อกรอผล hub_response นานถึง 45 วิ) ไปรันใน thread แยก
        # → event loop ของ MCP server ว่าง รับ request อื่นพร้อมกันได้ (ไม่ค้างทั้งเซิร์ฟเวอร์)
        # มาจาก App = ผู้ใช้สั่งจริง → อนุญาตคำสั่งปิด/รีสตาร์ทเครื่องได้
        return await asyncio.to_thread(agent.run, task, user_id=user_id or None, allow_power=True)
