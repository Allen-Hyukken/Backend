"""
Quiz routes — mirrors QuizController.java

POST   /api/quizzes                    (TEACHER)
GET    /api/quizzes/<id>?teacher=true  (any authenticated)
GET    /api/quizzes?classroomId=<id>   (any authenticated)
DELETE /api/quizzes/<id>               (TEACHER)
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
    result = quiz_service.get_by_classroom(classroom_id)
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