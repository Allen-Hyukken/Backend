"""
ClassroomService — mirrors ClassroomService.java

create()           Teacher creates a classroom (auto-generates code if blank)
get_my_classrooms() Returns classrooms for the current user (teacher or student)
get_detail()       Full classroom info including quizzes
join_by_code()     Student joins a classroom via code
upload_banner()    Teacher uploads a banner image (stored as BLOB)
get_banner()       Returns raw banner bytes
"""

import uuid
from extensions import db
from models import Classroom, User, UserRole


def create(data: dict, teacher_email: str) -> dict:
    teacher = _find_user(teacher_email)

    name = data.get("name", "").strip()
    if not name:
        raise ValueError("name: must not be blank")

    code = data.get("code", "")
    if not code or not code.strip():
        code = uuid.uuid4().hex[:8].upper()

    classroom = Classroom(name=name, code=code, teacher=teacher)
    db.session.add(classroom)
    db.session.commit()
    return _to_response(classroom)


def get_my_classrooms(email: str) -> list:
    user = _find_user(email)
    if user.role == UserRole.TEACHER:
        rooms = Classroom.query.filter_by(teacher_id=user.id).all()
    else:
        rooms = user.enrolled_classrooms.all()
    return [_to_response(c) for c in rooms]


def get_detail(classroom_id: int) -> dict:
    c = Classroom.query.get(classroom_id)
    if not c:
        raise RuntimeError("Classroom not found")

    resp = _to_response(c)
    resp["quizzes"] = [_quiz_summary(q) for q in c.quizzes]
    return resp


def join_by_code(code: str, student_email: str) -> None:
    classroom = Classroom.query.filter_by(code=code).first()
    if not classroom:
        raise RuntimeError(f"Classroom not found with code: {code}")
    student = _find_user(student_email)
    if student not in classroom.students.all():
        classroom.students.append(student)
        db.session.commit()


def upload_banner(classroom_id: int, file, teacher_email: str) -> None:
    classroom = Classroom.query.get(classroom_id)
    if not classroom:
        raise RuntimeError("Classroom not found")
    classroom.banner_image        = file.read()
    classroom.banner_content_type = file.content_type
    db.session.commit()


def get_banner(classroom_id: int):
    classroom = Classroom.query.get(classroom_id)
    if not classroom:
        raise RuntimeError("Classroom not found")
    return classroom.banner_image, classroom.banner_content_type


# ── Helpers ───────────────────────────────────────────────────────────────────
def _find_user(email: str) -> User:
    user = User.query.filter_by(email=email).first()
    if not user:
        raise RuntimeError(f"User not found: {email}")
    return user


def _to_response(c: Classroom) -> dict:
    return {
        "id":           c.id,
        "name":         c.name,
        "code":         c.code,
        "teacherId":    c.teacher.id   if c.teacher else None,
        "teacherName":  c.teacher.name if c.teacher else None,
        "studentCount": c.students.count(),
        "quizCount":    c.quizzes.count(),
        "hasBanner":    c.banner_image is not None,
    }


def _quiz_summary(q) -> dict:
    return {
        "id":            q.id,
        "title":         q.title,
        "description":   q.description,
        "published":     q.published,
        "questionCount": len(q.questions),
        "totalPoints":   q.total_points,
        "createdAt":     q.created_at.isoformat() if q.created_at else None,
        "teacherName":   q.teacher.name if q.teacher else None,
    }