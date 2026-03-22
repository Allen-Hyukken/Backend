"""
QuizService

Fix vs original:
  _to_summary() now includes  classRoomId  and  classRoomName  because
  Flutter's QuizModel.fromJson reads both fields:
      classRoomId:   j['classRoomId'] ?? 0,
      classRoomName: j['classRoomName'],
"""

from extensions import db
from models import Quiz, Question, Choice, Classroom, User, QuestionType


def create(data: dict, teacher_email: str) -> dict:
    teacher = _find_user(teacher_email)

    title        = data.get("title", "").strip()
    classroom_id = data.get("classroomId")

    if not title:
        raise ValueError("title: must not be blank")
    if not classroom_id:
        raise ValueError("classroomId: must not be null")

    classroom = Classroom.query.get(classroom_id)
    if not classroom:
        raise RuntimeError("Classroom not found")

    quiz = Quiz(
        title       = title,
        description = data.get("description"),
        published   = data.get("published", True),
        classroom   = classroom,
        teacher     = teacher,
    )

    questions_data = data.get("questions") or []
    questions      = []
    total_points   = 0.0

    for idx, qd in enumerate(questions_data):
        q_text = qd.get("text", "").strip()
        q_type = qd.get("type", "")
        if not q_text:
            raise ValueError(f"questions[{idx}].text: must not be blank")
        if q_type not in [t.value for t in QuestionType]:
            raise ValueError(f"questions[{idx}].type: invalid value '{q_type}'")

        q_index      = qd.get("qIndex", idx) or idx
        points       = float(qd.get("points", 1.0))
        total_points += points

        question = Question(
            quiz           = quiz,
            q_index        = q_index,
            type           = QuestionType(q_type),
            text           = q_text,
            correct_answer = qd.get("correctAnswer"),
            points         = points,
        )

        for cd in (qd.get("choices") or []):
            c_text = cd.get("text", "").strip()
            if not c_text:
                raise ValueError("choice text must not be blank")
            question.choices.append(
                Choice(text=c_text, correct=bool(cd.get("correct", False)))
            )

        questions.append(question)

    quiz.questions    = questions
    quiz.total_points = total_points

    db.session.add(quiz)
    db.session.commit()
    return _to_summary(quiz)


def get_detail(quiz_id: int, teacher_view: bool = False) -> dict:
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        raise RuntimeError("Quiz not found")

    resp = _to_summary(quiz)
    resp["questions"] = [_to_question_response(q, teacher_view) for q in quiz.questions]
    return resp


def get_by_classroom(classroom_id: int) -> list:
    quizzes = Quiz.query.filter_by(classroom_id=classroom_id).all()
    return [_to_summary(q) for q in quizzes]


def delete(quiz_id: int, teacher_email: str) -> None:
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        raise RuntimeError("Quiz not found")
    if quiz.teacher.email != teacher_email:
        raise PermissionError("Not authorized")
    db.session.delete(quiz)
    db.session.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────
def _find_user(email: str) -> User:
    user = User.query.filter_by(email=email).first()
    if not user:
        raise RuntimeError("User not found")
    return user


def _to_summary(q: Quiz) -> dict:
    # FIX: added classRoomId + classRoomName — required by Flutter's QuizModel.fromJson
    return {
        "id":            q.id,
        "title":         q.title,
        "description":   q.description,
        "published":     q.published,
        "classRoomId":   q.classroom_id,
        "classRoomName": q.classroom.name if q.classroom else None,
        "questionCount": len(q.questions),
        "totalPoints":   q.total_points,
        "createdAt":     q.created_at.isoformat() if q.created_at else None,
        "teacherName":   q.teacher.name if q.teacher else None,
    }


def _to_question_response(q: Question, teacher_view: bool) -> dict:
    resp = {
        "id":     q.id,
        "text":   q.text,
        "type":   q.type.value,
        "qIndex": q.q_index,
        "points": q.points,
        "choices": [
            {
                "id":   c.id,
                "text": c.text,
                **({"correct": c.correct} if teacher_view else {}),
            }
            for c in q.choices
        ],
    }
    if teacher_view:
        resp["correctAnswer"] = q.correct_answer
    return resp


def get_quiz_leaderboard(quiz_id: int) -> list:
    from models import Attempt

    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        raise RuntimeError("Quiz not found")

    # Get all attempts for this quiz
    attempts = Attempt.query.filter_by(quiz_id=quiz_id).all()

    leaderboard = []
    for attempt in attempts:
        student = attempt.student
        leaderboard.append({
            "userId":      student.id,
            "name":        student.name,
            "score":       round(attempt.score or 0, 1),
            "totalPoints": round(quiz.total_points or 0, 1),
            "percent":     round((attempt.score or 0) / quiz.total_points * 100)
                           if quiz.total_points else 0,
            "submittedAt": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        })

    # Sort by score descending
    leaderboard.sort(key=lambda x: x["score"], reverse=True)

    # Add rank
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard