"""
Auth routes — mirrors AuthController.java

POST /api/auth/register
POST /api/auth/login
"""

from flask import Blueprint, request, jsonify
from services import auth_service

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    try:
        result = auth_service.register(data)
        return jsonify(result), 200
    except LookupError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 422


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    try:
        result = auth_service.login(data)
        return jsonify(result), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 401
    except ValueError as e:
        return jsonify({"error": str(e)}), 422