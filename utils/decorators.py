"""
Role-based access decorators — mirrors Spring's @PreAuthorize annotations.

Usage:
    @teacher_required   →  @PreAuthorize("hasRole('TEACHER')")
    @student_required   →  @PreAuthorize("hasRole('STUDENT')")
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from models import User


def _get_current_user():
    email = get_jwt_identity()
    return User.query.filter_by(email=email).first()


def teacher_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_current_user()
        if user is None or user.role.value != "TEACHER":
            return jsonify({"error": "Access denied"}), 403
        return fn(*args, **kwargs)
    return wrapper


def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_current_user()
        if user is None or user.role.value != "STUDENT":
            return jsonify({"error": "Access denied"}), 403
        return fn(*args, **kwargs)
    return wrapper


def get_current_user():
    """Helper — call inside a jwt_required route to get the User object."""
    return _get_current_user()