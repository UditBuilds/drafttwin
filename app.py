import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import db
from auth import auth_bp, login_manager, User
from brain_generator import generate_brain_md
from brain_editor import SECTIONS, assemble_brain, bump_minor, parse_sections
from llm import draft_reply

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
app.teardown_appcontext(db.close_db)

login_manager.init_app(app)
app.register_blueprint(auth_bp)

BRAINS_DIR = Path(__file__).parent / "brains"
BRAINS_DIR.mkdir(exist_ok=True)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "brand"


def _write_brain_to_disk(brand_id: int, name: str, brain_md: str) -> None:
    path = BRAINS_DIR / f"{brand_id}-{_slug(name)}.md"
    path.write_text(brain_md, encoding="utf-8")


@app.route("/")
def index():
    if current_user.is_authenticated:
        if not current_user.has_brain:
            return redirect(url_for("onboarding"))
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


# --- Onboarding -------------------------------------------------------------

@app.route("/onboarding", methods=["GET"])
@login_required
def onboarding():
    if current_user.has_brain:
        return redirect(url_for("dashboard"))
    return render_template("onboarding.html")


@app.route("/onboarding", methods=["POST"])
@login_required
def onboarding_submit():
    form = request.form

    names = form.getlist("product_name[]")
    prices = form.getlist("product_price[]")
    descs = form.getlist("product_description[]")
    products = []
    for n, p, d in zip(names, prices, descs):
        if (n or "").strip():
            products.append({"name": n, "price": p, "description": d})

    never_list = [form.get(f"never_{i}", "") for i in range(1, 6)]

    data = {
        "brand_name": form.get("brand_name", "").strip(),
        "brand_description": form.get("brand_description", "").strip(),
        "target_customer": form.get("target_customer", "").strip(),
        "tone_preference": form.get("tone_preference", "").strip(),
        "products": products,
        "shipping_policy": form.get("shipping_policy", "").strip(),
        "return_policy": form.get("return_policy", "").strip(),
        "payment_methods": form.get("payment_methods", "").strip(),
        "never_list": never_list,
    }

    if not data["brand_name"]:
        return render_template("onboarding.html", error="Brand name is required."), 400

    brain_md = generate_brain_md(data)

    db.save_brand_onboarding(
        brand_id=current_user.id,
        name=data["brand_name"],
        brain_md=brain_md,
        form_json=json.dumps(data, ensure_ascii=False),
    )
    _write_brain_to_disk(current_user.id, data["brand_name"], brain_md)

    return redirect(url_for("dashboard"))


# --- Dashboard --------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    brand = db.get_brand(current_user.id)
    if not brand or not brand["brain_md"]:
        return redirect(url_for("onboarding"))

    drafts = db.recent_drafts(current_user.id, limit=20)
    return render_template(
        "dashboard.html",
        brand=brand,
        drafts=drafts,
    )


# --- Brain editor -----------------------------------------------------------

@app.route("/brain", methods=["GET"])
@login_required
def brain_editor():
    brand = db.get_brand(current_user.id)
    if not brand or not brand["brain_md"]:
        return redirect(url_for("onboarding"))

    sections = parse_sections(brand["brain_md"])
    return render_template(
        "brain.html",
        brand=brand,
        sections=sections,
        section_meta=SECTIONS,
    )


@app.route("/brain", methods=["POST"])
@login_required
def brain_save():
    brand = db.get_brand(current_user.id)
    if not brand or not brand["brain_md"]:
        return redirect(url_for("onboarding"))

    new_sections = {
        f"section_{n}": request.form.get(f"section_{n}", "").strip()
        for n, _ in SECTIONS
    }
    internal = request.form.get("internal", "").strip()

    new_version = bump_minor(brand["version"] or "1.0")
    new_md = assemble_brain(brand["name"], new_version, new_sections, internal)

    db.update_brain(current_user.id, new_md, new_version)
    _write_brain_to_disk(current_user.id, brand["name"], new_md)

    return redirect(url_for("brain_editor"))


# --- Drafting API -----------------------------------------------------------

@app.route("/api/draft", methods=["POST"])
@login_required
def api_draft():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify(error="message is required"), 400

    brand = db.get_brand(current_user.id)
    if not brand or not brand["brain_md"]:
        return jsonify(error="no brand brain available — complete onboarding first"), 400

    try:
        result = draft_reply(brand["brain_md"], message)
    except Exception as e:
        return jsonify(error=f"LLM call failed: {e}"), 500

    draft_id = db.save_draft(
        brand_id=current_user.id,
        customer_msg=message,
        classification=result["classification"],
        reply=result["reply"],
        reasoning=result["reasoning"],
    )

    return jsonify({**result, "draft_id": draft_id})


# --- Flagging ---------------------------------------------------------------

@app.route("/api/flag", methods=["POST"])
@login_required
def api_flag():
    payload = request.get_json(silent=True) or {}
    try:
        draft_id = int(payload.get("draft_id"))
    except (TypeError, ValueError):
        return jsonify(error="draft_id required"), 400

    suggested = (payload.get("suggested_reply") or "").strip()
    if not suggested:
        return jsonify(error="suggested_reply required"), 400

    # Ownership check
    if not db.get_draft(draft_id, current_user.id):
        return jsonify(error="draft not found"), 404

    db.upsert_flag(draft_id, current_user.id, suggested)
    return jsonify(ok=True)


@app.route("/flagged")
@login_required
def flagged_page():
    brand = db.get_brand(current_user.id)
    if not brand or not brand["brain_md"]:
        return redirect(url_for("onboarding"))

    flags = db.flagged_drafts_for_brand(current_user.id, include_resolved=True)
    return render_template("flagged.html", brand=brand, flags=flags)


@app.route("/api/flag/resolve", methods=["POST"])
@login_required
def api_flag_resolve():
    payload = request.get_json(silent=True) or {}
    try:
        flag_id = int(payload.get("flag_id"))
    except (TypeError, ValueError):
        return jsonify(error="flag_id required"), 400
    db.resolve_flag(flag_id, current_user.id)
    return jsonify(ok=True)


@app.route("/api/flag/delete", methods=["POST"])
@login_required
def api_flag_delete():
    payload = request.get_json(silent=True) or {}
    try:
        flag_id = int(payload.get("flag_id"))
    except (TypeError, ValueError):
        return jsonify(error="flag_id required"), 400
    db.delete_flag(flag_id, current_user.id)
    return jsonify(ok=True)


with app.app_context():
    db.init_db()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
