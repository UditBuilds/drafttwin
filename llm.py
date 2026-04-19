"""Groq SDK wrapper. Uses tool-use (OpenAI-compatible function calling) to force
structured JSON output matching the shape the rest of the app expects."""

import json
import os

from groq import Groq

MODEL = "llama-3.3-70b-versatile"

_client = None


def client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


DRAFT_TOOL = {
    "type": "function",
    "function": {
        "name": "draft_reply",
        "description": (
            "Classify the customer message and draft a reply strictly in the brand's "
            "voice as defined in the brain file. Never invent facts. If the answer "
            "isn't covered by the brain, classify as ESCALATE."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "classification": {
                    "type": "string",
                    "enum": ["AUTO", "DRAFT+APPROVE", "ESCALATE"],
                    "description": (
                        "AUTO = safe to send as-is. "
                        "DRAFT+APPROVE = founder must approve before sending (refunds, "
                        "replacements, money commitments, ambiguous complaints). "
                        "ESCALATE = pause and hand to founder (legal, medical, PR, "
                        "anything violating the Never List, anything not covered)."
                    ),
                },
                "reply": {
                    "type": "string",
                    "description": "The reply text in the brand's voice, ready to send or review.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One short sentence: why this classification.",
                },
            },
            "required": ["classification", "reply", "reasoning"],
        },
    },
}


SYSTEM_INSTRUCTIONS = """\
You are the customer support digital twin for the brand described in the BRAND BRAIN FILE above.

Rules you must follow on every single reply:
1. Use ONLY the information in the brain file. Never invent prices, policies, timelines, product details, or facts that are not written there.
2. If the customer asks something not covered by the brain → classify ESCALATE.
3. Apply the Never List strictly. If fulfilling the request would violate any Never List item → ESCALATE.
4. Match the brand's tone rules exactly (length, emoji policy, language mirroring).
5. For anything involving money commitments (refunds, replacements, goodwill, discounts) → at minimum DRAFT+APPROVE, unless the brain explicitly auto-approves it.
6. Legal, medical, PR/media, threats of public posts, reseller/wholesale → always ESCALATE.

You MUST respond by calling the `draft_reply` tool. Do not reply in plain text."""


def draft_reply(brain_md: str, customer_message: str):
    """Return dict with keys: classification, reply, reasoning."""
    resp = client().chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": "BRAND BRAIN FILE:\n\n" + brain_md + "\n\n" + SYSTEM_INSTRUCTIONS,
            },
            {"role": "user", "content": customer_message},
        ],
        tools=[DRAFT_TOOL],
        tool_choice={"type": "function", "function": {"name": "draft_reply"}},
    )

    choice = resp.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None) or []
    for tc in tool_calls:
        if tc.function.name != "draft_reply":
            continue
        try:
            args = json.loads(tc.function.arguments)
        except (json.JSONDecodeError, TypeError):
            break
        return {
            "classification": args.get("classification", "ESCALATE"),
            "reply": args.get("reply", ""),
            "reasoning": args.get("reasoning", ""),
        }

    return {
        "classification": "ESCALATE",
        "reply": "",
        "reasoning": "Model did not return a tool call.",
    }
