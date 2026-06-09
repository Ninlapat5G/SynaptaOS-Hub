"""
workflow — สมองของ Hub แบบ event-driven (LlamaIndex Workflow)

loop เครื่องมือ (tool-calling agent) + reflect:
  prepare → call_llm → (มี tool_call?) → run_tools → call_llm → ... → ตอบ
  tool พลาด → แทรก "บทเรียน" เข้าบทสนทนา ให้คิดวิธีใหม่ ไม่ทำซ้ำผิดเดิม (Reflexion-lite)

model-agnostic ผ่าน OpenAILike (ชี้ Ollama@DGX) — เปลี่ยนโมเดลไม่ต้องแก้ที่นี่
"""
import logging

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.workflow import (Context, Event, StartEvent, StopEvent,
                                       Workflow, step)

_log = logging.getLogger("brain.workflow")

# มาร์กว่าผล tool คือความล้มเหลว (เทียบ string ฟรี ไม่ใช้ LLM) — แนวเดียวกับ reflect ฝั่ง App
_FAIL_MARKERS = ("[error]", "✗", "ผิดพลาด", "ไม่สำเร็จ", "ไม่พบ")


def _is_fail(text: str) -> bool:
    t = (text or "").lower()
    return any(m.lower() in t for m in _FAIL_MARKERS)


class ToolCallEvent(Event):
    pass


class LLMInputEvent(Event):
    pass


class StreamEvent(Event):
    """เหตุการณ์ที่เขียนออก stream เพื่อให้ฝั่งเรียกโชว์ความคืบหน้าสด (tool_start/tool_end)"""
    payload: dict


class HubBrain(Workflow):
    """1 instance ต่อ 1 งาน (ถือ tools/prompt/history ของงานนั้น) — state ต่อรอบเก็บใน ctx.store"""

    def __init__(self, llm, tools, system_prompt, history, max_iterations=10, **kw):
        super().__init__(timeout=None, **kw)
        self.llm = llm
        self.tools = tools
        self.tools_by_name = {t.metadata.name: t for t in tools}
        self.system_prompt = system_prompt
        self.history = history or []
        self.max_iterations = max_iterations

    @step
    async def prepare(self, ctx: Context, ev: StartEvent) -> LLMInputEvent:
        chat = [ChatMessage(role=MessageRole.SYSTEM, content=self.system_prompt)]
        for h in self.history[-10:]:        # ประวัติ multi-turn (เหมือน ReAct เดิม)
            text = (h.get("text") or "").strip()
            if not text:
                continue
            role = MessageRole.USER if h.get("role") == "user" else MessageRole.ASSISTANT
            chat.append(ChatMessage(role=role, content=text))
        chat.append(ChatMessage(role=MessageRole.USER, content=ev.task))
        await ctx.store.set("chat", chat)
        await ctx.store.set("iter", 0)
        await ctx.store.set("retries", 0)
        return LLMInputEvent()

    @step
    async def call_llm(self, ctx: Context, ev: LLMInputEvent) -> ToolCallEvent | StopEvent:
        it = await ctx.store.get("iter")
        if it >= self.max_iterations:    # กันวนไม่จบ (เทียบเท่า recursion_limit ของ ReAct)
            return StopEvent(result="ทำหลายขั้นแล้วแต่ยังไม่เสร็จค่ะ ลองแยกเป็นคำสั่งย่อย ๆ ดูนะคะ 🙏")
        await ctx.store.set("iter", it + 1)
        chat = await ctx.store.get("chat")
        resp = await self.llm.achat_with_tools(self.tools, chat_history=chat,
                                               allow_parallel_tool_calls=False)
        chat.append(resp.message)
        await ctx.store.set("chat", chat)
        tool_calls = self.llm.get_tool_calls_from_response(resp, error_on_no_tool_call=False)
        if not tool_calls:               # ไม่เรียก tool แล้ว = คำตอบสุดท้าย
            return StopEvent(result=str(resp.message.content or ""))
        await ctx.store.set("tool_calls", tool_calls)
        for tc in tool_calls:            # บอกฝั่งเรียกว่ากำลังจะเรียกเครื่องมืออะไร
            ctx.write_event_to_stream(StreamEvent(payload={
                "type": "tool_start", "name": tc.tool_name, "args": tc.tool_kwargs}))
        return ToolCallEvent()

    @step
    async def run_tools(self, ctx: Context, ev: ToolCallEvent) -> LLMInputEvent:
        chat = await ctx.store.get("chat")
        tool_calls = await ctx.store.get("tool_calls")
        retries = await ctx.store.get("retries")
        any_fail = False
        for tc in tool_calls:
            tool = self.tools_by_name.get(tc.tool_name)
            if tool is None:
                out, ok = f"[error] ไม่รู้จักเครื่องมือ {tc.tool_name}", False
            else:
                try:
                    out = str(await tool.acall(**tc.tool_kwargs))
                    ok = not _is_fail(out)
                except Exception as e:
                    out, ok = f"[error] {e}", False
            _log.info("  [%s] → %s", tc.tool_name, out[:120])
            ctx.write_event_to_stream(StreamEvent(payload={
                "type": "tool_end", "name": tc.tool_name, "result": out}))
            chat.append(ChatMessage(role=MessageRole.TOOL, content=out,
                        additional_kwargs={"name": tc.tool_name, "tool_call_id": tc.tool_id}))
            any_fail = any_fail or not ok
        # REFLECT: tool พลาด + ยังไม่เกินเพดาน → แทรกบทเรียนให้คิดวิธีใหม่ (ไม่ทำซ้ำเดิม)
        if any_fail and retries < 2:
            await ctx.store.set("retries", retries + 1)
            chat.append(ChatMessage(role=MessageRole.USER,
                content="[ระบบ] ขั้นที่แล้วมีเครื่องมือทำงานล้มเหลว — วิเคราะห์สาเหตุจากผลด้านบน "
                        "แล้วลองวิธีอื่นที่ต่างจากเดิม ถ้าแก้ไม่ได้จริง ๆ ให้บอกผู้ใช้สั้น ๆ ว่าติดตรงไหนค่ะ"))
        await ctx.store.set("chat", chat)
        return LLMInputEvent()
