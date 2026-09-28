import json
from time import time

import webauthn
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import UserVerificationRequirement

from app import security
from app.extensions import db
from app.models.passkey import PasskeyModel

login_bp = Blueprint("login", __name__)

# How long after a correct password the authenticator code may be entered.
TWO_FACTOR_WINDOW_SECONDS = 5 * 60


def _safe_next() -> str:
    """Where to go after signing in: a path on this site only."""
    target = session.pop("next", None) or url_for("home.index")
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return url_for("home.index")
    return target


def _locked_out_message() -> str | None:
    wait = security.seconds_until_unlocked()
    if wait:
        return f"Too many failed attempts. Try again in {max(1, wait // 60)} minute(s)."
    return None


@login_bp.route("/login", methods=["GET", "POST"])
def login():
    if not security.auth_required() or security.is_signed_in():
        return redirect(url_for("home.index"))

    has_passkeys = db.session.query(PasskeyModel.id).first() is not None
    if request.method == "GET":
        return render_template("login/index.html", has_passkeys=has_passkeys)

    locked = _locked_out_message()
    if locked:
        flash(locked, "error")
        return render_template("login/index.html", has_passkeys=has_passkeys), 429

    if not security.check_password(request.form.get("password", "")):
        security.record_failed_attempt()
        flash("Incorrect password", "error")
        return render_template("login/index.html", has_passkeys=has_passkeys), 401

    if security.totp_enabled():
        session["password_ok_at"] = time()
        return redirect(url_for("login.two_factor"))

    security.clear_failed_attempts()
    target = _safe_next()
    security.sign_in()
    return redirect(target)


@login_bp.route("/login/2fa", methods=["GET", "POST"])
def two_factor():
    password_ok_at = session.get("password_ok_at")
    if not security.auth_required() or not password_ok_at or time() - password_ok_at > TWO_FACTOR_WINDOW_SECONDS:
        session.pop("password_ok_at", None)
        return redirect(url_for("login.login"))

    if request.method == "GET":
        return render_template("login/two_factor.html")

    locked = _locked_out_message()
    if locked:
        flash(locked, "error")
        return render_template("login/two_factor.html"), 429

    if not security.verify_totp(security.get_setting("auth_totp_secret"), request.form.get("code", "")):
        security.record_failed_attempt()
        flash("That code didn't work. Check your authenticator app and try again.", "error")
        return render_template("login/two_factor.html"), 401

    security.clear_failed_attempts()
    target = _safe_next()
    security.sign_in()
    return redirect(target)


@login_bp.route("/login/passkey/options", methods=["POST"])
def passkey_options():
    if not security.auth_required():
        return jsonify({"error": "Sign in is not enabled"}), 400
    options = webauthn.generate_authentication_options(
        rp_id=security.webauthn_rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session["passkey_challenge"] = bytes_to_base64url(options.challenge)
    return jsonify(json.loads(webauthn.options_to_json(options)))


@login_bp.route("/login/passkey/verify", methods=["POST"])
def passkey_verify():
    challenge = session.pop("passkey_challenge", None)
    if not security.auth_required() or not challenge:
        return jsonify({"error": "Start the passkey sign in again"}), 400
    locked = _locked_out_message()
    if locked:
        return jsonify({"error": locked}), 429

    credential = request.get_json(silent=True) or {}
    passkey = db.session.query(PasskeyModel).filter_by(credential_id=credential.get("id", "")).one_or_none()
    if passkey is None:
        security.record_failed_attempt()
        return jsonify({"error": "This passkey isn't registered here"}), 401
    try:
        verified = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=webauthn.base64url_to_bytes(challenge),
            expected_rp_id=security.webauthn_rp_id(),
            expected_origin=security.webauthn_expected_origins(),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as e:  # noqa: BLE001 - any verification failure is a failed sign in
        security.record_failed_attempt()
        security.log.warning(f"Passkey sign in failed: {e}")
        return jsonify({"error": "Passkey sign in failed"}), 401

    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = int(time())
    db.session.commit()
    security.clear_failed_attempts()
    target = _safe_next()
    security.sign_in()
    return jsonify({"redirect": target})


@login_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    if security.auth_required():
        flash("Signed out")
        return redirect(url_for("login.login"))
    return redirect(url_for("home.index"))
