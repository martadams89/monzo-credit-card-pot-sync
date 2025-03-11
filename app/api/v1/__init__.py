from flask import Blueprint, jsonify

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# A sample route to confirm the blueprint is working
@api_v1_bp.route("/", methods=["GET"])
def index():
    return jsonify({"message": "API v1 is running"})
