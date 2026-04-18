"""Split the brain.md into editable sections, and reassemble it on save.

The brain generator produces a fixed structure (5 numbered sections + internal
notes). The editor keeps those section titles constant and only lets the founder
edit the body text under each one. On save we bump the minor version and
regenerate the header + footer — so the file stays well-formed.
"""

import re
from datetime import datetime

SECTIONS = [
    (1, "BRAND & VOICE"),
    (2, "PRODUCTS & PRICING"),
    (3, "OPERATIONS & CUSTOMER SUPPORT"),
    (4, "DECISION RULES"),
    (5, "THE NEVER LIST"),
]

SECTION_HEADING_RE = re.compile(r"^## SECTION (\d+) — .+$", re.MULTILINE)
INTERNAL_HEADING_RE = re.compile(r"^## INTERNAL NOTES.*$", re.MULTILINE)
FOOTER_RE = re.compile(r"\n\s*---\s*\n\s*\*End of brain file.*?\*\s*$", re.DOTALL)


def _strip_trailing_separator(body: str) -> str:
    return re.sub(r"\n\s*---\s*$", "", body).strip()


def parse_sections(md: str) -> dict:
    """Return {'section_1': body, ..., 'section_5': body, 'internal': body}."""
    result = {f"section_{n}": "" for n, _ in SECTIONS}
    result["internal"] = ""
    if not md:
        return result

    section_matches = list(SECTION_HEADING_RE.finditer(md))
    internal_match = INTERNAL_HEADING_RE.search(md)

    for i, m in enumerate(section_matches):
        num = int(m.group(1))
        start = m.end()
        if i + 1 < len(section_matches):
            end = section_matches[i + 1].start()
        elif internal_match and internal_match.start() > start:
            end = internal_match.start()
        else:
            end = len(md)
        result[f"section_{num}"] = _strip_trailing_separator(md[start:end])

    if internal_match:
        body = md[internal_match.end():]
        body = FOOTER_RE.sub("", body)
        result["internal"] = _strip_trailing_separator(body)

    return result


def assemble_brain(brand_name: str, version: str, sections: dict, internal_body: str) -> str:
    today = datetime.utcnow().strftime("%B %Y")
    out = []
    out.append(f"# {brand_name.upper()} — DIGITAL TWIN BRAIN FILE")
    out.append(f"### Version {version} | Last Updated: {today}")
    out.append("### Status: Production")
    out.append("")
    out.append("---")
    out.append("")
    out.append(
        f"> **What this file is:** The complete knowledge base for {brand_name}'s "
        f"AI customer support twin. This file is loaded as context for every "
        f"customer interaction. The twin uses ONLY the information in this file — "
        f"never invents, guesses, or improvises beyond what's written here."
    )
    out.append("")
    out.append("---")
    out.append("")

    for num, title in SECTIONS:
        body = (sections.get(f"section_{num}") or "").strip()
        out.append(f"## SECTION {num} — {title}")
        out.append("")
        out.append(body)
        out.append("")
        out.append("---")
        out.append("")

    out.append("## INTERNAL NOTES (for twin logic, not customer-facing)")
    out.append("")
    out.append((internal_body or "").strip())
    out.append("")
    out.append("---")
    out.append("")
    out.append(f"*End of brain file. Version {version} — last updated {today}.*")
    out.append("")
    return "\n".join(out)


def bump_minor(version: str) -> str:
    """'1.0' -> '1.1'. Resilient to malformed input."""
    try:
        major_str, minor_str = version.split(".", 1)
        return f"{int(major_str)}.{int(minor_str) + 1}"
    except (ValueError, AttributeError):
        return "1.1"
