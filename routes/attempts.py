"""
Attempt routes — mirrors AttemptController.java

POST   /api/attempts           (STUDENT) — submit quiz
GET    /api/attempts/<id>      (any authenticated) — view one attempt
GET    /api/attempts/me        (STUDENT) — all my attempts
PATCH  /api/attempts/grade     (TEACHER) — manually grade essay/coding
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services import attempt_service
from utils.decorators import teacher_required, student_required

attempt_bp = Blueprint("attempts", __name__, url_prefix="/api/attempts")


@attempt_bp.post("")
@student_required
def submit():
    data = request.get_json(silent=True) or {}
    try:
        result = attempt_service.submit(data, get_jwt_identity())
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


# NOTE: /me must be registered BEFORE /<id> to avoid Flask matching "me" as an int
@attempt_bp.get("/me")
@student_required
def get_my_attempts():
    try:
        result = attempt_service.get_my_attempts(get_jwt_identity())
        return jsonify(result), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@attempt_bp.get("/<int:attempt_id>")
@jwt_required()
def get_attempt(attempt_id):
    try:
        result = attempt_service.get_attempt(attempt_id)
        return jsonify(result), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404


@attempt_bp.patch("/grade")
@teacher_required
def grade():
    data = request.get_json(silent=True) or {}
    try:
        attempt_service.grade_answer(data)
        return jsonify({}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400