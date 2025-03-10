from flask import Blueprint, render_template, current_app

home_bp = Blueprint("home", __name__)

@home_bp.route("/")
def index():
    """Home page."""
    return render_template("home/index.html")

@home_bp.route("/features")
def features():
    """Features page."""
    return render_template("home/features.html")

@home_bp.route("/about")
def about():
    """About page."""
    return render_template("home/about.html")

@home_bp.route("/privacy")
def privacy():
    """Privacy policy page."""
    return render_template("home/privacy.html")

@home_bp.route("/terms")
def terms():
    """Terms of service page."""
    return render_template("home/terms.html")

@home_bp.route("/contact")
def contact():
    """Contact page."""
    return render_template("home/contact.html")
