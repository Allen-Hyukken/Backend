"""
AttemptService — mirrors AttemptService.java

submit()        Student submits answers; auto-grades MCQ / TF / IDENT
get_attempt()   Fetch one attempt result by ID
get_my_attempts() All attempts for the logged-in student
grade_answer()  Teacher manually grades an ESSAY or CODING answer
"""

from extensions import db
from models import Attempt, Answer, Quiz, User, Question, QuestionType


def submit(data: dict, student_email: str) -> dict:
    quiz_id = data.get("quizId")
    if not quiz_id:
        raise ValueError("quizId: must not be null")

    student = _find_user(student_email)
    quiz    = Quiz.query.get(quiz_id)
    if not quiz:
        raise RuntimeError("Quiz not found")

    submitted_answers: dict = data.get("answers") or {}

    attempt = Attempt(quiz=quiz, student=student, score=0.0)
    db.session.add(attempt)
    db.session.flush()   # get attempt.id before adding answers

    score   = 0.0
    answers = []

    for question in quiz.questions:
        # answers keys come in as strings from JSON
        given_text = submitted_answers.get(str(question.id)) or submitted_answers.get(question.id)

        answer = Answer(
            attempt    = attempt,
            question   = question,
            given_text = given_text,
            correct    = False,
        )

        if question.type == QuestionType.MCQ:
            if given_text:
                try:
                    choice_id = int(given_text)
                    choice = next(
                        (c for c in question.choices if c.id == choice_id), None
                    )
                    if choice:
                        answer.choice   = choice
                        answer.correct  = choice.correct
                        if answer.correct:
                            score += question.points
                except (ValueError, TypeError):
                    pass

        elif question.type == QuestionType.TF:
            if given_text and question.correct_answer:
                answer.correct = given_text.strip().lower() == question.correct_answer.strip().lower()
                if answer.correct:
                    score += question.points

        elif question.type == QuestionType.IDENT:
            if given_text and question.correct_answer:
                answer.correct = given_text.strip().lower() == question.correct_answer.strip().lower()
                if answer.correct:
                    score += question.points

        elif question.type in (QuestionType.ESSAY, QuestionType.CODING):
            # Stored; teacher grades manually later
            answer.correct = False

        answers.append(answer)

    attempt.answers = answers
    attempt.score   = score
    db.session.commit()
    return _to_response(attempt)


def get_attempt(attempt_id: int) -> dict:
    attempt = Attempt.query.get(attempt_id)
    if not attempt:
        raise RuntimeError("Attempt not found")
    return _to_response(attempt)


def get_my_attempts(student_email: str) -> list:
    student = _find_user(student_email)
    attempts = Attempt.query.filter_by(student_id=student.id).all()
    return [_to_response(a) for a in attempts]


def grade_answer(data: dict) -> None:
    answer_id = data.get("answerId")
    score_val = data.get("score")

    if answer_id is None:
        raise ValueError("answerId: must not be null")
    if score_val is None:
        raise ValueError("score: must not be null")

    answer = Answer.query.get(answer_id)
    if not answer:
        raise RuntimeError("Answer not found")

    answer.essay_score = float(score_val)
    answer.correct     = float(score_val) > 0

    # Recalculate total attempt score
    attempt = answer.attempt
    total = sum(
        (a.essay_score if a.essay_score is not None else (a.question.points if a.correct else 0.0))
        for a in attempt.answers
    )
    attempt.score = total
    db.session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _find_user(email: str) -> User:
    user = User.query.filter_by(email=email).first()
    if not user:
        raise RuntimeError("User not found")
    return user


def _to_response(attempt: Attempt) -> dict:
    answered = sum(
        1 for a in attempt.answers
        if a.given_text is not None or a.choice_id is not None
    )
    total_q = len(attempt.answers)

    return {
        "attemptId":      attempt.id,
        "quizId":         attempt.quiz.id,
        "quizTitle":      attempt.quiz.title,
        "score":          attempt.score,
        "totalPoints":    attempt.quiz.total_points,
        "totalQuestions": total_q,
        "answeredCount":  answered,
        "skippedCount":   total_q - answered,
        "submittedAt":    attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "answers": [
            {
                "questionId":   a.question_id,
                "questionText": a.question.text,
                "givenText":    a.given_text,
                "choiceId":     a.choice_id,
                "correct":      a.correct,
                "essayScore":   a.essay_score,
            }
            for a in attempt.answers
        ],
    }