from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    try:
        from app.database.connection import get_db
        db = get_db()
        db.command("ping")
        return jsonify({
            "success": True,
            "message": "Service healthy",
            "database": "connected"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Service unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 503