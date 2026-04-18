"""Anthropic SDK wrapper. Uses tool-use to force structured JSON output
and prompt caching on the (large, reused) brain.md system prompt."""

import os
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

_client = None


def client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


DRAFT_TOOL = {
    "name": "draft_reply",
    "description": (
        "Classify the customer message and draft a reply strictly in the brand's "
        "voice as defined in the brain file. Never invent facts. If the answer "
        "isn't covered by the brain, classify as ESCALATE."
    ),
    "input_schema": {
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
    resp = client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": "BRAND BRAIN FILE:\n\n" + brain_md,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": SYSTEM_INSTRUCTIONS,
            },
        ],
        tools=[DRAFT_TOOL],
        tool_choice={"type": "tool", "name": "draft_reply"},
        messages=[{"role": "user", "content": customer_message}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == "draft_reply":
            out = block.input
            return {
                "classification": out.get("classification", "ESCALATE"),
                "reply": out.get("reply", ""),
                "reasoning": out.get("reasoning", ""),
            }

    return {
        "classification": "ESCALATE",
        "reply": "",
        "reasoning": "Model did not return a tool call.",
    }
