"""
AttemptService — mirrors AttemptService.java

submit()          Student submits answers; enforces deadline; auto-grades MCQ/TF/IDENT/CODING
get_attempt()     Fetch one attempt result by ID
get_my_attempts() All attempts for the logged-in student
grade_answer()    Teacher manually grades an ESSAY answer
"""

import re
from datetime import datetime
from extensions import db
from models import Attempt, Answer, Quiz, QuizStatus, User, Question, QuestionType


# ── Code normalization (mirrors QuizService.java normalizeCode) ────────────────

def _normalize_code(code: str) -> str:
    """
    Strips comments, collapses whitespace, and lowercases so that two
    functionally identical code snippets compare as equal even if the
    student used different indentation or formatting.

    Steps mirror the Java QuizService.normalizeCode method exactly:
      1. Remove // single-line comments
      2. Remove /* … */ block comments
      3. Collapse runs of spaces/tabs to a single space
      4. Remove whitespace around common operators/punctuation
      5. Strip and join non-empty lines
      6. Lowercase everything
    """
    if not code:
        return ""

    # 1. Remove single-line comments (// to end of line)
    code = re.sub(r'//[^\n]*', '', code)

    # 2. Remove block comments (/* … */)  — DOTALL so . matches newlines
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

    # 3. Collapse spaces/tabs
    code = re.sub(r'[ \t]+', ' ', code)

    # 4. Remove whitespace around operators and punctuation
    code = re.sub(r'\s*([{};(),=+\-*/<>!&|])\s*', r'\1', code)

    # 5. Join non-empty lines (strip each line first)
    lines  = re.split(r'\r?\n', code)
    result = ''.join(line.strip() for line in lines if line.strip())

    # 6. Lowercase
    return result.lower()


def _compare_code(student: str, correct: str) -> bool:
    """Returns True when both code snippets are functionally equivalent."""
    return _normalize_code(student) == _normalize_code(correct)


# ── Submission ─────────────────────────────────────────────────────────────────

def submit(data: dict, student_email: str) -> dict:
    quiz_id = data.get("quizId")
    if not quiz_id:
        raise ValueError("quizId: must not be null")

    student = _find_user(student_email)
    quiz    = Quiz.query.get(quiz_id)
    if not quiz:
        raise RuntimeError("Quiz not found")

    # ── Status check — only ACTIVE quizzes can be attempted ──────────────────
    if quiz.status != QuizStatus.ACTIVE:
        raise ValueError("This quiz has not been deployed yet.")

    # ── Published check (legacy belt-and-suspenders) ──────────────────────────
    if quiz.published is False:
        raise ValueError("This quiz is not currently available.")

    # ── Deadline enforcement ──────────────────────────────────────────────────
    if quiz.deadline and quiz.deadline < datetime.utcnow():
        raise ValueError("The deadline for this quiz has passed.")

    submitted_answers: dict = data.get("answers") or {}

    attempt = Attempt(quiz=quiz, student=student, score=0.0)
    db.session.add(attempt)
    db.session.flush()   # get attempt.id before adding answers

    score   = 0.0
    answers = []

    for question in quiz.questions:
        given_text = (
            submitted_answers.get(str(question.id))
            or submitted_answers.get(question.id)
        )

        answer = Answer(
            attempt    = attempt,
            question   = question,
            given_text = given_text,
            correct    = False,
        )

        qpoints = question.points if question.points is not None else 1.0

        if question.type == QuestionType.MCQ:
            if given_text:
                try:
                    choice_id = int(given_text)
                    choice = next(
                        (c for c in question.choices if c.id == choice_id), None
                    )
                    if choice:
                        answer.choice  = choice
                        answer.correct = choice.correct
                        if answer.correct:
                            score += qpoints
                except (ValueError, TypeError):
                    pass

        elif question.type == QuestionType.TF:
            if given_text and question.correct_answer:
                answer.correct = (
                    given_text.strip().upper() == question.correct_answer.strip().upper()
                )
                if answer.correct:
                    score += qpoints

        elif question.type == QuestionType.IDENT:
            if given_text and question.correct_answer:
                answer.correct = (
                    given_text.strip().lower() == question.correct_answer.strip().lower()
                )
                if answer.correct:
                    score += qpoints

        elif question.type == QuestionType.CODING:
            # Auto-grade: normalise both sides before comparing.
            # Mirrors Java QuizService.compareCode / normalizeCode exactly.
            if given_text and question.correct_answer:
                answer.correct = _compare_code(given_text, question.correct_answer)
                if answer.correct:
                    score += qpoints
            # correct remains False when student left the editor empty

        elif question.type == QuestionType.ESSAY:
            answer.correct = False  # always requires manual teacher grading

        answers.append(answer)

    attempt.answers = answers
    attempt.score   = score
    db.session.commit()
    return _to_response(attempt)


# ── Fetch ──────────────────────────────────────────────────────────────────────

def get_attempt(attempt_id: int) -> dict:
    attempt = Attempt.query.get(attempt_id)
    if not attempt:
        raise RuntimeError("Attempt not found")
    return _to_response(attempt)


def get_my_attempts(student_email: str) -> list:
    student  = _find_user(student_email)
    attempts = Attempt.query.filter_by(student_id=student.id).all()
    return [_to_response(a) for a in attempts]


# ── Essay grading ──────────────────────────────────────────────────────────────

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

    if answer.question.type != QuestionType.ESSAY:
        raise ValueError("Only ESSAY answers can be manually graded")

    max_points = answer.question.points if answer.question.points is not None else 1.0
    score_val  = float(score_val)

    if score_val < 0 or score_val > max_points:
        raise ValueError(f"Score must be between 0 and {max_points}")

    answer.essay_score = score_val
    answer.correct     = score_val > 0

    # Recalculate total attempt score
    attempt = answer.attempt
    total   = 0.0
    for a in attempt.answers:
        q      = a.question
        qpts   = q.points if q.points is not None else 1.0
        if q.type == QuestionType.ESSAY:
            if a.essay_score is not None:
                total += a.essay_score
        elif a.correct:
            total += qpts
    attempt.score = total
    db.session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_display_text(answer) -> str:
    from models import Choice
    if answer.choice_id is not None:
        if answer.choice and hasattr(answer.choice, 'text'):
            return answer.choice.text
        choice = Choice.query.get(answer.choice_id)
        if choice:
            return choice.text
        return answer.given_text or str(answer.choice_id)
    return answer.given_text or ''


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
    quiz    = attempt.quiz

    return {
        "attemptId":      attempt.id,
        "quizId":         quiz.id if quiz else None,
        "quizTitle":      quiz.title if quiz else "",
        "showAnswers":    bool(quiz.show_answers) if quiz else False,
        "score":          attempt.score,
        "totalPoints":    quiz.total_points if quiz else 0,
        "totalQuestions": total_q,
        "answeredCount":  answered,
        "skippedCount":   total_q - answered,
        "submittedAt":    attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "answers": [
            {
                "questionId":   a.question_id,
                "questionText": a.question.text,
                "questionType": a.question.type.value,
                "givenText":    _get_display_text(a),
                "choiceId":     a.choice_id,
                "correct":      a.correct,
                "essayScore":   a.essay_score,
                # Include the correct answer text so Flutter's ReviewScreen
                # can show it when showAnswers is true.
                "correctAnswer": (
                    a.question.correct_answer
                    if a.question.type != QuestionType.MCQ
                    else next(
                        (c.text for c in a.question.choices if c.correct),
                        None,
                    )
                ),
            }
            for a in attempt.answers
        ],
    }