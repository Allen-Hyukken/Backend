"""
ClassroomService — mirrors ClassroomService.java
"""

import uuid
from sqlalchemy.exc import IntegrityError
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
    else:
        code = code.strip().upper()

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
    if not code:
        raise ValueError("Class code is required")

    # Normalize: codes are always stored uppercase
    code = code.strip().upper()

    classroom = Classroom.query.filter_by(code=code).first()
    if not classroom:
        raise RuntimeError(f"No classroom found with code '{code}'. Check the code and try again.")

    student = _find_user(student_email)

    # ── Proper DB-level duplicate check ──────────────────────────────────────
    # Do NOT use `student not in classroom.students.all()` — that loads the
    # entire student list into Python and the identity comparison is unreliable
    # with SQLAlchemy dynamic relationships loaded across different queries.
    already_enrolled = classroom.students.filter_by(id=student.id).first() is not None
    if already_enrolled:
        # Idempotent — joining twice is not an error from the client's perspective
        return

    try:
        classroom.students.append(student)
        db.session.commit()
    except IntegrityError:
        # Race condition: another request enrolled this student between the
        # check above and the INSERT.  Roll back and treat as success.
        db.session.rollback()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Could not join classroom: {e}") from e


def remove_student(classroom_id: int, student_id: int, teacher_email: str) -> None:
    """Teacher removes a student from their classroom."""
    classroom = Classroom.query.get(classroom_id)
    if not classroom:
        raise RuntimeError("Classroom not found")

    teacher = _find_user(teacher_email)
    if classroom.teacher_id != teacher.id:
        raise PermissionError("Only the classroom teacher can remove students")

    student = classroom.students.filter_by(id=student_id).first()
    if student is None:
        raise RuntimeError("Student is not enrolled in this classroom")

    try:
        classroom.students.remove(student)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"Could not remove student: {e}") from e


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


def get_leaderboard(classroom_id: int) -> list:
    from models import Attempt

    classroom = Classroom.query.get(classroom_id)
    if not classroom:
        raise RuntimeError("Classroom not found")

    students = classroom.students.all()
    quiz_ids = [q.id for q in classroom.quizzes]

    if not quiz_ids:
        return []

    leaderboard = []
    for student in students:
        attempts = Attempt.query.filter(
            Attempt.student_id == student.id,
            Attempt.quiz_id.in_(quiz_ids)
        ).all()

        total_score   = sum(a.score or 0 for a in attempts)
        total_points  = sum(a.quiz.total_points or 0 for a in attempts)
        quizzes_taken = len(attempts)

        leaderboard.append({
            "userId":       student.id,
            "name":         student.name,
            "totalScore":   round(total_score,  1),
            "totalPoints":  round(total_points, 1),
            "quizzesTaken": quizzes_taken,
            "percent":      round(total_score / total_points * 100) if total_points > 0 else 0,
        })

    leaderboard.sort(key=lambda x: x["totalScore"], reverse=True)
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard


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