from flask import Blueprint, render_template, current_app, redirect, url_for, flash, request
from app.extensions import mail
from flask_mail import Message

home_bp = Blueprint("home", __name__)

@home_bp.route("/")
def index():
    """Landing page."""
    return render_template("home/index.html")

@home_bp.route("/features")
def features():
    """Features page."""
    return render_template("home/features.html")

@home_bp.route("/about")
def about():
    """About page."""
    return render_template("home/about.html")

@home_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact page."""
    return render_template("home/contact.html")

@home_bp.route("/contact/submit", methods=["POST"])
def contact_submit():
    """Process contact form submission."""
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Validate input
        if not all([name, email, subject, message]):
            flash("Please fill in all fields", "error")
            return redirect(url_for("home.contact"))
        
        # Send email to admin
        admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
        
        msg = Message(
            subject=f"Contact Form: {subject}",
            recipients=[admin_email],
            body=f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\nMessage:\n{message}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        mail.send(msg)
        
        # Send confirmation to user
        user_msg = Message(
            subject="We've received your message",
            recipients=[email],
            body=f"Dear {name},\n\nThank you for contacting us. We have received your message and will get back to you shortly.\n\nBest regards,\nThe Monzo Sync Team",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        mail.send(user_msg)
        
        flash("Your message has been sent! We'll get back to you soon.", "success")
        return redirect(url_for("home.index"))
    except Exception as e:
        current_app.logger.error(f"Error sending contact form: {str(e)}")
        flash("An error occurred while sending your message. Please try again later.", "error")
        return redirect(url_for("home.contact"))
