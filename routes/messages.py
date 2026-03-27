# routes/messages.py
#
# Messaging system:
#   Announcements  — teacher → whole class (read-only for students)
#   Class chat     — everyone in a classroom (group chat)
#   Direct messages — student↔student, student↔teacher (private)

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from utils.decorators import teacher_required

messages_bp = Blueprint('messages', __name__, url_prefix='/api')

# ── Table creation ─────────────────────────────────────────────────────────────

def create_message_tables():
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS announcements (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            classroom_id INT NOT NULL,
            teacher_id   INT NOT NULL,
            teacher_name VARCHAR(120) NOT NULL,
            title        VARCHAR(200) NOT NULL,
            body         TEXT NOT NULL,
            created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_ann_classroom (classroom_id)
        )
    """))
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS class_messages (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            classroom_id INT NOT NULL,
            sender_id    INT NOT NULL,
            sender_name  VARCHAR(120) NOT NULL,
            sender_role  VARCHAR(20)  NOT NULL,
            body         TEXT NOT NULL,
            created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_cm_classroom (classroom_id),
            INDEX idx_cm_created  (created_at)
        )
    """))
    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS direct_messages (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            classroom_id  INT NOT NULL,
            sender_id     INT NOT NULL,
            sender_name   VARCHAR(120) NOT NULL,
            sender_role   VARCHAR(20)  NOT NULL,
            receiver_id   INT NOT NULL,
            receiver_name VARCHAR(120) NOT NULL,
            body          TEXT NOT NULL,
            created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_dm_sender   (sender_id),
            INDEX idx_dm_receiver (receiver_id),
            INDEX idx_dm_class    (classroom_id)
        )
    """))
    db.session.commit()
    print('[messages] Tables ready.')

# ── Helpers ────────────────────────────────────────────────────────────────────

def _current_user():
    from models import User
    email = get_jwt_identity()
    user  = User.query.filter_by(email=email).first()
    if not user:
        raise PermissionError('User not found')
    return user

def _is_in_classroom(user, classroom_id: int) -> bool:
    """
    Returns True if the user is either the teacher of the classroom
    or an enrolled student.
    NOTE: your table is named 'classroom' (not 'classrooms').
    """
    row = db.session.execute(db.text("""
        SELECT 1 FROM classroom c
        LEFT JOIN classroom_students cs
            ON cs.classroom_id = c.id AND cs.student_id = :uid
        WHERE c.id = :cid
          AND (c.teacher_id = :uid OR cs.student_id = :uid)
        LIMIT 1
    """), {'uid': user.id, 'cid': classroom_id}).fetchone()
    return row is not None

# ── ANNOUNCEMENTS ──────────────────────────────────────────────────────────────

@messages_bp.post('/classrooms/<int:classroom_id>/announcements')
@teacher_required
def post_announcement(classroom_id):
    user  = _current_user()
    data  = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    body  = (data.get('body')  or '').strip()
    if not title or not body:
        return jsonify({'error': 'title and body are required'}), 422
    db.session.execute(db.text("""
        INSERT INTO announcements
            (classroom_id, teacher_id, teacher_name, title, body)
        VALUES (:cid, :tid, :tname, :title, :body)
    """), {'cid': classroom_id, 'tid': user.id,
           'tname': user.name, 'title': title, 'body': body})
    db.session.commit()
    return jsonify({'ok': True}), 200


@messages_bp.get('/classrooms/<int:classroom_id>/announcements')
@jwt_required()
def get_announcements(classroom_id):
    user = _current_user()
    if not _is_in_classroom(user, classroom_id):
        return jsonify({'error': 'Access denied'}), 403
    rows = db.session.execute(db.text("""
        SELECT id, teacher_name, title, body, created_at
        FROM   announcements
        WHERE  classroom_id = :cid
        ORDER  BY created_at DESC LIMIT 50
    """), {'cid': classroom_id}).fetchall()
    return jsonify([{
        'id':          r[0],
        'teacherName': r[1],
        'title':       r[2],
        'body':        r[3],
        'createdAt':   r[4].isoformat(),
    } for r in rows]), 200


@messages_bp.delete('/announcements/<int:ann_id>')
@teacher_required
def delete_announcement(ann_id):
    user = _current_user()
    db.session.execute(db.text(
        'DELETE FROM announcements WHERE id=:id AND teacher_id=:tid'
    ), {'id': ann_id, 'tid': user.id})
    db.session.commit()
    return jsonify({'ok': True}), 200

# ── CLASS CHAT ─────────────────────────────────────────────────────────────────

@messages_bp.post('/classrooms/<int:classroom_id>/chat')
@jwt_required()
def send_class_message(classroom_id):
    user = _current_user()
    if not _is_in_classroom(user, classroom_id):
        return jsonify({'error': 'Access denied'}), 403
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'body is required'}), 422
    db.session.execute(db.text("""
        INSERT INTO class_messages
            (classroom_id, sender_id, sender_name, sender_role, body)
        VALUES (:cid, :sid, :sname, :srole, :body)
    """), {'cid': classroom_id, 'sid': user.id,
           'sname': user.name, 'srole': user.role.value, 'body': body})
    db.session.commit()
    return jsonify({'ok': True}), 200


@messages_bp.get('/classrooms/<int:classroom_id>/chat')
@jwt_required()
def get_class_messages(classroom_id):
    user  = _current_user()
    if not _is_in_classroom(user, classroom_id):
        return jsonify({'error': 'Access denied'}), 403
    since  = request.args.get('since')
    extra  = 'AND created_at > :since' if since else ''
    params = {'cid': classroom_id}
    if since:
        params['since'] = since
    rows = db.session.execute(db.text(f"""
        SELECT id, sender_id, sender_name, sender_role, body, created_at
        FROM   class_messages
        WHERE  classroom_id = :cid {extra}
        ORDER  BY created_at ASC LIMIT 100
    """), params).fetchall()
    return jsonify([{
        'id':         r[0],
        'senderId':   r[1],
        'senderName': r[2],
        'senderRole': r[3],
        'body':       r[4],
        'createdAt':  r[5].isoformat(),
        'isMe':       r[1] == user.id,
    } for r in rows]), 200

# ── DIRECT MESSAGES ────────────────────────────────────────────────────────────

@messages_bp.post('/classrooms/<int:classroom_id>/dm/<int:receiver_id>')
@jwt_required()
def send_dm(classroom_id, receiver_id):
    user = _current_user()
    if not _is_in_classroom(user, classroom_id):
        return jsonify({'error': 'Access denied'}), 403
    from models import User as UserModel
    receiver = UserModel.query.get(receiver_id)
    if not receiver:
        return jsonify({'error': 'Recipient not found'}), 404
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'body is required'}), 422
    db.session.execute(db.text("""
        INSERT INTO direct_messages
            (classroom_id, sender_id, sender_name, sender_role,
             receiver_id, receiver_name, body)
        VALUES (:cid, :sid, :sname, :srole, :rid, :rname, :body)
    """), {'cid': classroom_id, 'sid': user.id, 'sname': user.name,
           'srole': user.role.value, 'rid': receiver_id,
           'rname': receiver.name, 'body': body})
    db.session.commit()
    return jsonify({'ok': True}), 200


@messages_bp.get('/classrooms/<int:classroom_id>/dm/<int:other_id>')
@jwt_required()
def get_dm(classroom_id, other_id):
    user   = _current_user()
    if not _is_in_classroom(user, classroom_id):
        return jsonify({'error': 'Access denied'}), 403
    since  = request.args.get('since')
    extra  = 'AND created_at > :since' if since else ''
    params = {'cid': classroom_id, 'me': user.id, 'other': other_id}
    if since:
        params['since'] = since
    rows = db.session.execute(db.text(f"""
        SELECT id, sender_id, sender_name, sender_role, body, created_at
        FROM   direct_messages
        WHERE  classroom_id = :cid
          AND  ((sender_id = :me    AND receiver_id = :other)
             OR (sender_id = :other AND receiver_id = :me))
          {extra}
        ORDER  BY created_at ASC LIMIT 100
    """), params).fetchall()
    return jsonify([{
        'id':         r[0],
        'senderId':   r[1],
        'senderName': r[2],
        'senderRole': r[3],
        'body':       r[4],
        'createdAt':  r[5].isoformat(),
        'isMe':       r[1] == user.id,
    } for r in rows]), 200


@messages_bp.get('/classrooms/<int:classroom_id>/members')
@jwt_required()
def get_members(classroom_id):
    """All members (teacher + students) — used for DM picker."""
    user = _current_user()
    if not _is_in_classroom(user, classroom_id):
        return jsonify({'error': 'Access denied'}), 403
    rows = db.session.execute(db.text("""
        SELECT u.id, u.name, u.role
        FROM classroom c
        JOIN users u ON u.id = c.teacher_id
        WHERE c.id = :cid
        UNION
        SELECT u.id, u.name, u.role
        FROM classroom_students cs
        JOIN users u ON u.id = cs.student_id
        WHERE cs.classroom_id = :cid
    """), {'cid': classroom_id}).fetchall()
    return jsonify([{
        'id':   r[0],
        'name': r[1],
        'role': r[2] if isinstance(r[2], str) else r[2].value,
        'isMe': r[0] == user.id,
    } for r in rows]), 200