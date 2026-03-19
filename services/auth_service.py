"""
AuthService — mirrors AuthService.java

register()  →  validate uniqueness, hash password, save user, return JWT
login()     →  verify credentials, return JWT
"""

import bcrypt
from flask_jwt_extended import create_access_token
from extensions import db
from models import User, UserRole


def register(data: dict) -> dict:
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role_str = data.get("role", "")

    # ── Validation ────────────────────────────────────────────────────────────
    errors = []
    if not name:
        errors.append("name: must not be blank")
    if not email:
        errors.append("email: must not be blank")
    if not password or len(password) < 6:
        errors.append("password: must be at least 6 characters")
    if role_str not in [r.value for r in UserRole]:
        errors.append(f"role: must be one of {[r.value for r in UserRole]}")
    if errors:
        raise ValueError(", ".join(errors))

    # ── Uniqueness check (mirrors IllegalArgumentException → 409) ─────────────
    if User.query.filter_by(email=email).first():
        raise LookupError("Email already registered")

    # ── Persist ───────────────────────────────────────────────────────────────
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(name=name, email=email, password=hashed, role=UserRole(role_str))
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=user.email)
    return _auth_response(token, user)


def login(data: dict) -> dict:
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        raise ValueError("email and password are required")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password.encode()):
        raise PermissionError("Invalid email or password")

    token = create_access_token(identity=user.email)
    return _auth_response(token, user)


# ── Helper ────────────────────────────────────────────────────────────────────
def _auth_response(token: str, user: User) -> dict:
    return {
        "token": token,
        "id":    user.id,
        "name":  user.name,
        "email": user.email,
        "role":  user.role.value,
    }