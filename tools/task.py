"""
run_task — ส่งงานภาษาคนให้ agent ของ Hub คิด/ทำเอง (agent-to-agent)

App (plan-and-execute) เจอ step ที่ต้องให้ Hub ทำ → เรียก run_task →
Hub agent (ReAct) รับ sub-task เดียว ใช้ tool belt ทำจนเสร็จ แล้วคืนผลกลับ
"""


def register(mcp):
    import agent

    @mcp.tool()
    def run_task(task: str) -> str:
        """ส่งงานภาษาธรรมชาติให้ Hub ทำบนเครื่อง PC เช่น 'เปิดเพลง lofi', 'ดู disk ที่เหลือ', 'shutdown'. Hub จะคิดเองว่าต้องใช้คำสั่งอะไรแล้วลงมือทำ คืนผลลัพธ์สั้นๆ"""
        return agent.run(task)
