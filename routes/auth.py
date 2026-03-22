"""
Auth routes — mirrors AuthController.java

POST /api/auth/register
POST /api/auth/login
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

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

@auth_bp.get("/me")
@jwt_required()
def me():
    from flask_jwt_extended import get_jwt_identity
    from models import User
    email = get_jwt_identity()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Account not found"}), 401
    return jsonify({
        "id":    user.id,
        "name":  user.name,
        "email": user.email,
        "role":  user.role.value,
    }), 200