"""
SQLAlchemy models — mapped to quizdatabase MySQL schema.

Fixes vs original:
  1. All IDs use BigInteger to match MySQL BIGINT
  2. Quiz.classroom_id is mapped to the real column name  class_room_id
     (MySQL schema uses class_room_id, not classroom_id)
"""

import enum
from datetime import datetime
from extensions import db


# ── Many-to-many: classroom <-> students ──────────────────────────────────────
classroom_students = db.Table(
    "classroom_students",
    db.Column("classroom_id", db.BigInteger, db.ForeignKey("classroom.id"), primary_key=True),
    db.Column("student_id",   db.BigInteger, db.ForeignKey("users.id"),     primary_key=True),
)


# ── Enums ──────────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class QuestionType(str, enum.Enum):
    MCQ    = "MCQ"
    TF     = "TF"
    IDENT  = "IDENT"
    ESSAY  = "ESSAY"
    CODING = "CODING"


# ── User ───────────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    id       = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name     = db.Column(db.String(150))
    email    = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role     = db.Column(db.Enum(UserRole), nullable=False)

    taught_classrooms = db.relationship(
        "Classroom",
        back_populates="teacher",
        foreign_keys="Classroom.teacher_id",
        lazy="dynamic",
    )
    enrolled_classrooms = db.relationship(
        "Classroom",
        secondary=classroom_students,
        back_populates="students",
        lazy="dynamic",
    )


# ── Classroom ──────────────────────────────────────────────────────────────────
class Classroom(db.Model):
    __tablename__ = "classroom"

    id                  = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name                = db.Column(db.String(150), nullable=False)
    code                = db.Column(db.String(50),  unique=True)
    banner_image        = db.Column(db.LargeBinary)
    banner_content_type = db.Column(db.String(50))
    teacher_id          = db.Column(db.BigInteger, db.ForeignKey("users.id"))

    teacher  = db.relationship("User", back_populates="taught_classrooms",    foreign_keys=[teacher_id])
    students = db.relationship("User", secondary=classroom_students,           back_populates="enrolled_classrooms", lazy="dynamic")
    quizzes  = db.relationship("Quiz", back_populates="classroom",             cascade="all, delete-orphan", lazy="dynamic")


# ── Quiz ───────────────────────────────────────────────────────────────────────
class Quiz(db.Model):
    __tablename__ = "quiz"

    id          = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    published   = db.Column(db.Boolean, default=True)

    # FIX: MySQL column is class_room_id (not classroom_id)
    classroom_id = db.Column("class_room_id", db.BigInteger, db.ForeignKey("classroom.id"))

    teacher_id   = db.Column(db.BigInteger, db.ForeignKey("users.id"))
    total_points = db.Column(db.Float,      default=0.0)
    created_at   = db.Column(db.DateTime,   default=datetime.utcnow)

    classroom = db.relationship("Classroom", back_populates="quizzes")
    teacher   = db.relationship("User", foreign_keys=[teacher_id])
    questions = db.relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.q_index",
        lazy="select",
    )


# ── Question ───────────────────────────────────────────────────────────────────
class Question(db.Model):
    __tablename__ = "question"

    id             = db.Column(db.BigInteger,          primary_key=True, autoincrement=True)
    quiz_id        = db.Column(db.BigInteger,          db.ForeignKey("quiz.id"), nullable=False)
    q_index        = db.Column(db.Integer,             default=0)
    type           = db.Column(db.Enum(QuestionType),  nullable=False)
    text           = db.Column(db.Text,                nullable=False)
    correct_answer = db.Column(db.Text)
    points         = db.Column(db.Float,               default=1.0)

    quiz    = db.relationship("Quiz",   back_populates="questions")
    choices = db.relationship("Choice", back_populates="question", cascade="all, delete-orphan")


# ── Choice ─────────────────────────────────────────────────────────────────────
class Choice(db.Model):
    __tablename__ = "choice"

    id          = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    question_id = db.Column(db.BigInteger, db.ForeignKey("question.id"), nullable=False)
    text        = db.Column(db.Text,       nullable=False)
    correct     = db.Column(db.Boolean,    default=False)

    question = db.relationship("Question", back_populates="choices")


# ── Attempt ────────────────────────────────────────────────────────────────────
class Attempt(db.Model):
    __tablename__ = "attempt"

    id           = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    quiz_id      = db.Column(db.BigInteger, db.ForeignKey("quiz.id"),  nullable=False)
    student_id   = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    score        = db.Column(db.Float)
    submitted_at = db.Column(db.DateTime,   default=datetime.utcnow)

    quiz    = db.relationship("Quiz")
    student = db.relationship("User", foreign_keys=[student_id])
    answers = db.relationship("Answer", back_populates="attempt", cascade="all, delete-orphan")


# ── Answer ─────────────────────────────────────────────────────────────────────
class Answer(db.Model):
    __tablename__ = "answer"

    id          = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    attempt_id  = db.Column(db.BigInteger, db.ForeignKey("attempt.id"),  nullable=False)
    question_id = db.Column(db.BigInteger, db.ForeignKey("question.id"), nullable=False)
    choice_id   = db.Column(db.BigInteger, db.ForeignKey("choice.id"),   nullable=True)
    given_text  = db.Column(db.Text)
    correct     = db.Column(db.Boolean,    default=False)
    essay_score = db.Column(db.Float)

    attempt  = db.relationship("Attempt",  back_populates="answers")
    question = db.relationship("Question")
    choice   = db.relationship("Choice")
