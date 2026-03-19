"""
Classroom routes — mirrors ClassroomController.java

POST   /api/classrooms              (TEACHER)
GET    /api/classrooms              (any authenticated)
GET    /api/classrooms/<id>         (any authenticated)
POST   /api/classrooms/join?code=   (STUDENT)
POST   /api/classrooms/<id>/banner  (TEACHER, multipart)
GET    /api/classrooms/<id>/banner  (any authenticated)
"""

from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from services import classroom_service
from utils.decorators import teacher_required, student_required

classroom_bp = Blueprint("classrooms", __name__, url_prefix="/api/classrooms")


@classroom_bp.post("")
@teacher_required
def create():
    data = request.get_json(silent=True) or {}
    try:
        result = classroom_service.create(data, get_jwt_identity())
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@classroom_bp.get("")
@jwt_required()
def get_mine():
    try:
        result = classroom_service.get_my_classrooms(get_jwt_identity())
        return jsonify(result), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@classroom_bp.get("/<int:classroom_id>")
@jwt_required()
def get_detail(classroom_id):
    try:
        result = classroom_service.get_detail(classroom_id)
        return jsonify(result), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404


@classroom_bp.post("/join")
@student_required
def join():
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"error": "code query parameter is required"}), 422
    try:
        classroom_service.join_by_code(code, get_jwt_identity())
        return jsonify({}), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@classroom_bp.post("/<int:classroom_id>/banner")
@teacher_required
def upload_banner(classroom_id):
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 422
    try:
        classroom_service.upload_banner(classroom_id, file, get_jwt_identity())
        return jsonify({}), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400


@classroom_bp.get("/<int:classroom_id>/banner")
@jwt_required()
def get_banner(classroom_id):
    try:
        image_bytes, content_type = classroom_service.get_banner(classroom_id)
        if not image_bytes:
            return jsonify({"error": "No banner found"}), 404
        ct = content_type or "image/jpeg"
        return Response(image_bytes, mimetype=ct), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400