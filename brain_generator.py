"""Converts onboarding form data into a structured brain.md for the brand."""

from datetime import datetime
from textwrap import dedent


def _products_table(products):
    if not products:
        return "_No products added yet._"
    rows = ["| Product | Price | Description |", "|---------|-------|-------------|"]
    for p in products:
        name = (p.get("name") or "").strip()
        price = (p.get("price") or "").strip()
        desc = (p.get("description") or "").strip().replace("\n", " ")
        if not name:
            continue
        rows.append(f"| {name} | {price} | {desc} |")
    return "\n".join(rows)


def _never_list(items):
    numbered = []
    for i, item in enumerate(items, start=1):
        text = (item or "").strip()
        if not text:
            continue
        numbered.append(f"{i}. **NEVER** {text}")
    if not numbered:
        return "_No hard rules defined yet._"
    return "\n".join(numbered)


def generate_brain_md(data):
    """Build a brain.md string from form data.

    `data` fields expected:
      brand_name, brand_description, target_customer, tone_preference,
      products: list[{name, price, description}],
      shipping_policy, return_policy, payment_methods,
      never_list: list[str] (up to 5)
    """
    today = datetime.utcnow().strftime("%B %Y")

    brand = data["brand_name"].strip()
    description = data["brand_description"].strip()
    customer = data["target_customer"].strip()
    tone = data["tone_preference"].strip()
    shipping = data["shipping_policy"].strip()
    returns = data["return_policy"].strip()
    payments = data["payment_methods"].strip()

    products_md = _products_table(data.get("products", []))
    never_md = _never_list(data.get("never_list", []))

    md = dedent(f"""\
        # {brand.upper()} — DIGITAL TWIN BRAIN FILE
        ### Version 1.0 | Last Updated: {today}
        ### Status: Phase 1 Production

        ---

        > **What this file is:** The complete knowledge base for {brand}'s AI customer support twin. This file is loaded as context for every customer interaction. The twin uses ONLY the information in this file — never invents, guesses, or improvises beyond what's written here.

        ---

        ## SECTION 1 — BRAND & VOICE

        ### What We Are
        {description}

        ### Our Customer
        {customer}

        ### Tone Rules
        {tone}

        ---

        ## SECTION 2 — PRODUCTS & PRICING

        {products_md}

        ---

        ## SECTION 3 — OPERATIONS & CUSTOMER SUPPORT

        ### 3.1 Shipping
        {shipping}

        ### 3.2 Returns & Exchanges
        {returns}

        ### 3.3 Payments
        {payments}

        ---

        ## SECTION 4 — DECISION RULES

        ### Legend
        - 🟢 **AUTO** — twin replies solo, no approval needed
        - 🟡 **DRAFT+APPROVE** — twin writes the reply, founder approves before it sends
        - 🔴 **ESCALATE** — twin pauses, pings founder, founder takes over directly

        ### Default Routing
        | # | Situation | Rule |
        |---|-----------|------|
        | 1 | General product question answerable from this brain | 🟢 AUTO |
        | 2 | Order status / tracking question | 🟢 AUTO |
        | 3 | Customer hasn't shared order ID — ask for it | 🟢 AUTO |
        | 4 | Damaged / wrong / missing item complaint | 🟡 DRAFT+APPROVE |
        | 5 | Payment deducted but order didn't place | 🟡 DRAFT+APPROVE |
        | 6 | Refund request | 🟡 DRAFT+APPROVE |
        | 7 | Discount request outside documented rules | 🟡 DRAFT+APPROVE |
        | 8 | Anything that would violate the Never List | 🔴 ESCALATE |
        | 9 | Legal / consumer court / lawyer mention | 🔴 ESCALATE |
        | 10 | Media / press / PR mention | 🔴 ESCALATE |
        | 11 | Threat to post negatively on social media | 🔴 ESCALATE |
        | 12 | Allergic reaction / medical symptoms claim | 🔴 ESCALATE |
        | 13 | Reseller / white-label / wholesale inquiry | 🔴 ESCALATE |
        | 14 | Request for information not covered in this brain | 🔴 ESCALATE |
        | 15 | Customer asks to speak to founder/owner | 🔴 ESCALATE |
        | 16 | Sustained aggression / 2+ profanities / caps rant | 🔴 ESCALATE |
        | 17 | Flirty / inappropriate (first instance) | 🟢 AUTO — one cold redirect |
        | 18 | Flirty / inappropriate (continues after redirect) | 🔴 ESCALATE |

        ### Default Handoff Line (for ESCALATE holding replies)
        > "Understood — Team {brand} will personally look into this and get back to you shortly."

        ---

        ## SECTION 5 — THE NEVER LIST

        {never_md}

        ---

        ## INTERNAL NOTES (for twin logic, not customer-facing)

        - If a customer asks about anything not covered in this brain → ESCALATE rather than guess.
        - Never invent prices, policies, timelines, or product facts that aren't written above.
        - Match the language the customer writes in (within the tone rules above).
        - Keep replies concise and in the brand's voice as defined in Section 1.

        ---

        *End of brain file. Version 1.0 — generated from onboarding form on {today}.*
    """)

    return md
