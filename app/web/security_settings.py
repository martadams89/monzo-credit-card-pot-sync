import json
from time import time

import qrcode
import qrcode.image.svg
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
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app import security
from app.extensions import db
from app.models.passkey import PasskeyModel

security_bp = Blueprint("security", __name__)


def _passkeys() -> list[PasskeyModel]:
    return db.session.query(PasskeyModel).order_by(PasskeyModel.id).all()


def _current_password_ok() -> bool:
    """Sensitive changes need the current password, unless none is set yet or the
    app was started with POT_SYNC_DISABLE_AUTH to recover from a lock-out."""
    if security.get_setting("auth_password_hash") is None or security.auth_disabled_by_env():
        return True
    if security.check_password(request.form.get("current_password", "")):
        return True
    flash("Current password is incorrect", "error")
    return False


@security_bp.route("/", methods=["GET"])
def index():
    return render_template(
        "settings/security.html",
        mode=security.auth_mode(),
        password_set=security.get_setting("auth_password_hash") is not None,
        totp_enabled=security.totp_enabled(),
        passkeys=_passkeys(),
        disabled_by_env=security.auth_disabled_by_env(),
        rp_id=security.webauthn_rp_id(),
        min_length=security.MIN_PASSWORD_LENGTH,
    )


@security_bp.route("/password", methods=["POST"])
def set_password():
    if not _current_password_ok():
        return redirect(url_for("security.index"))
    password = request.form.get("new_password", "")
    if len(password) < security.MIN_PASSWORD_LENGTH:
        flash(f"Use at least {security.MIN_PASSWORD_LENGTH} characters", "error")
        return redirect(url_for("security.index"))
    if password != request.form.get("confirm_password", ""):
        flash("The passwords don't match", "error")
        return redirect(url_for("security.index"))

    security.set_password(password)
    if security.auth_required():
        # Changing the password signs out other sessions; keep this one signed in.
        security.sign_in()
    flash("Password saved")
    return redirect(url_for("security.index"))


@security_bp.route("/mode", methods=["POST"])
def set_mode():
    mode = request.form.get("mode")
    if mode not in (security.AUTH_MODE_NONE, security.AUTH_MODE_PASSWORD):
        flash("Unknown sign in option", "error")
        return redirect(url_for("security.index"))
    if not _current_password_ok():
        return redirect(url_for("security.index"))
    if mode == security.AUTH_MODE_PASSWORD and security.get_setting("auth_password_hash") is None:
        flash("Set a password before turning on sign in", "error")
        return redirect(url_for("security.index"))

    security.set_setting("auth_mode", mode)
    security.bump_session_version()
    if mode == security.AUTH_MODE_PASSWORD:
        security.sign_in()
        flash("Sign in is on. You'll need your password (or a passkey) to open Pot Sync.")
    else:
        session.clear()
        flash("Sign in is off. Anyone who can reach Pot Sync can use it.")
    return redirect(url_for("security.index"))


@security_bp.route("/totp", methods=["GET"])
def totp_setup():
    if security.totp_enabled():
        return redirect(url_for("security.index"))
    secret = session.get("pending_totp_secret") or security.new_totp_secret()
    session["pending_totp_secret"] = secret
    uri = security.totp_uri(secret)
    qr_svg = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2).to_string(encoding="unicode")
    return render_template("settings/totp.html", secret=secret, qr_svg=qr_svg)


@security_bp.route("/totp", methods=["POST"])
def totp_enable():
    secret = session.get("pending_totp_secret")
    if not secret:
        return redirect(url_for("security.totp_setup"))
    security.set_setting("auth_totp_last_step", "-1")
    if not security.verify_totp(secret, request.form.get("code", "")):
        flash("That code didn't work. Check the time on your phone and try the next code.", "error")
        return redirect(url_for("security.totp_setup"))
    security.set_setting("auth_totp_secret", secret)
    session.pop("pending_totp_secret", None)
    flash("Two-factor authentication is on")
    return redirect(url_for("security.index"))


@security_bp.route("/totp/disable", methods=["POST"])
def totp_disable():
    if not _current_password_ok():
        return redirect(url_for("security.index"))
    security.set_setting("auth_totp_secret", "")
    flash("Two-factor authentication is off")
    return redirect(url_for("security.index"))


@security_bp.route("/passkeys/options", methods=["POST"])
def passkey_register_options():
    user_id = security.get_setting("auth_user_handle")
    if user_id is None:
        user_id = bytes_to_base64url(webauthn.helpers.generate_user_handle())
        security.set_setting("auth_user_handle", user_id)
    options = webauthn.generate_registration_options(
        rp_id=security.webauthn_rp_id(),
        rp_name="Monzo Credit Card Pot Sync",
        user_name="pot-sync",
        user_display_name="Pot Sync",
        user_id=webauthn.base64url_to_bytes(user_id),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(p.credential_id)) for p in _passkeys()
        ],
    )
    session["passkey_registration_challenge"] = bytes_to_base64url(options.challenge)
    return jsonify(json.loads(webauthn.options_to_json(options)))


@security_bp.route("/passkeys", methods=["POST"])
def passkey_register():
    challenge = session.pop("passkey_registration_challenge", None)
    payload = request.get_json(silent=True) or {}
    if not challenge:
        return jsonify({"error": "Start adding the passkey again"}), 400
    try:
        verified = webauthn.verify_registration_response(
            credential=payload.get("credential") or {},
            expected_challenge=webauthn.base64url_to_bytes(challenge),
            expected_rp_id=security.webauthn_rp_id(),
            expected_origin=security.webauthn_expected_origins(),
            require_user_verification=True,
        )
    except Exception as e:  # noqa: BLE001 - report any verification failure to the page
        security.log.warning(f"Passkey registration failed: {e}")
        return jsonify({"error": "The passkey couldn't be verified"}), 400

    name = (payload.get("name") or "").strip()[:100] or f"Passkey {len(_passkeys()) + 1}"
    db.session.add(PasskeyModel(
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        name=name,
        created_at=int(time()),
    ))
    db.session.commit()
    flash(f"Passkey \"{name}\" added")
    return jsonify({"redirect": url_for("security.index")})


@security_bp.route("/passkeys/<int:passkey_id>/delete", methods=["POST"])
def passkey_delete(passkey_id: int):
    passkey = db.session.get(PasskeyModel, passkey_id)
    if passkey is not None:
        db.session.delete(passkey)
        db.session.commit()
        flash(f"Passkey \"{passkey.name}\" removed")
    return redirect(url_for("security.index"))
