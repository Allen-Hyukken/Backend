"""
Quiz routes — mirrors QuizController.java

POST   /api/quizzes                    (TEACHER)
GET    /api/quizzes/<id>?teacher=true  (any authenticated)
GET    /api/quizzes?classroomId=<id>   (any authenticated)
DELETE /api/quizzes/<id>               (TEACHER)
POST   /api/quizzes/<id>/deploy        (TEACHER) — publish to students
POST   /api/quizzes/<id>/retract       (TEACHER) — pull back to draft
GET    /api/quizzes/<id>/leaderboard   (any authenticated)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services import quiz_service
from utils.decorators import teacher_required

quiz_bp = Blueprint("quizzes", __name__, url_prefix="/api/quizzes")


@quiz_bp.post("")
@teacher_required
def create():
    data = request.get_json(silent=True) or {}
    try:
        result = quiz_service.create(data, get_jwt_identity())
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@quiz_bp.get("/<int:quiz_id>")
@jwt_required()
def get_detail(quiz_id):
    teacher_view = request.args.get("teacher", "false").lower() == "true"
    try:
        result = quiz_service.get_detail(quiz_id, teacher_view)
        return jsonify(result), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404


@quiz_bp.get("")
@jwt_required()
def get_by_classroom():
    classroom_id = request.args.get("classroomId", type=int)
    if not classroom_id:
        return jsonify({"error": "classroomId query parameter is required"}), 422

    # Teacher may pass ?all=true to see DRAFT quizzes too.
    # Students never pass this flag (and Flutter blocks TEACHER login anyway).
    show_all = request.args.get("all", "false").lower() == "true"
    result   = quiz_service.get_by_classroom(classroom_id, active_only=not show_all)
    return jsonify(result), 200


@quiz_bp.delete("/<int:quiz_id>")
@teacher_required
def delete(quiz_id):
    try:
        quiz_service.delete(quiz_id, get_jwt_identity())
        return jsonify({}), 204
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404


# ── Deploy / Retract ───────────────────────────────────────────────────────────

@quiz_bp.post("/<int:quiz_id>/deploy")
@teacher_required
def deploy(quiz_id):
    """
    Makes a DRAFT quiz ACTIVE so students can see and attempt it.
    Idempotent — deploying an already-active quiz is a no-op.
    """
    try:
        result = quiz_service.deploy(quiz_id, get_jwt_identity())
        return jsonify(result), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404


@quiz_bp.post("/<int:quiz_id>/retract")
@teacher_required
def retract(quiz_id):
    """
    Moves an ACTIVE quiz back to DRAFT, hiding it from students.
    """
    try:
        result = quiz_service.retract(quiz_id, get_jwt_identity())
        return jsonify(result), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404


# ── Leaderboard ────────────────────────────────────────────────────────────────

@quiz_bp.get("/<int:quiz_id>/leaderboard")
@jwt_required()
def get_quiz_leaderboard(quiz_id):
    try:
        result = quiz_service.get_quiz_leaderboard(quiz_id)
        return jsonify(result), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404