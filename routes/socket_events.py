# routes/socket_events.py
#
# WebSocket event handlers using Flask-SocketIO
#
# Rooms used:
#   classroom_{id}        — class chat room (all members)
#   dm_{min_id}_{max_id}  — private DM room (two users only)
#
# Flow:
#   1. Flutter connects with JWT token as auth
#   2. Flutter joins a room (join_classroom or join_dm)
#   3. Flutter emits send_class_message or send_dm
#   4. Server saves to DB and broadcasts to the room instantly

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_jwt_extended import decode_token
from extensions import db


def _get_user_from_token(token: str):
    """Decode JWT and return the User object."""
    from models import User
    try:
        decoded = decode_token(token)
        identity = decoded.get('sub')
        return User.query.filter_by(email=identity).first()
    except Exception:
        return None


def _is_in_classroom(user_id: int, classroom_id: int) -> bool:
    row = db.session.execute(db.text("""
        SELECT 1 FROM classroom c
        LEFT JOIN classroom_students cs
            ON cs.classroom_id = c.id AND cs.student_id = :uid
        WHERE c.id = :cid
          AND (c.teacher_id = :uid OR cs.student_id = :uid)
        LIMIT 1
    """), {'uid': user_id, 'cid': classroom_id}).fetchone()
    return row is not None


def register_socket_events(socketio: SocketIO):

    # ── Connection ──────────────────────────────────────────────────────────

    @socketio.on('connect')
    def on_connect(auth):
        """
        Flutter connects with: { token: 'Bearer eyJ...' }
        We verify the JWT here. If invalid, disconnect immediately.
        """
        if not auth or not auth.get('token'):
            return False  # reject connection
        token = auth['token'].replace('Bearer ', '').strip()
        user = _get_user_from_token(token)
        if not user:
            return False  # reject — invalid token

    @socketio.on('disconnect')
    def on_disconnect():
        pass  # cleanup handled automatically by Flask-SocketIO

    # ── Class chat rooms ────────────────────────────────────────────────────

    @socketio.on('join_classroom')
    def on_join_classroom(data):
        """
        Flutter emits: { token: '...', classroomId: 5 }
        Server joins the socket to room 'classroom_5'
        """
        token        = (data.get('token') or '').replace('Bearer ', '').strip()
        classroom_id = data.get('classroomId')
        user = _get_user_from_token(token)
        if not user or not classroom_id:
            return
        if not _is_in_classroom(user.id, int(classroom_id)):
            return
        room = f'classroom_{classroom_id}'
        join_room(room)
        emit('joined', {'room': room})

    @socketio.on('leave_classroom')
    def on_leave_classroom(data):
        classroom_id = data.get('classroomId')
        if classroom_id:
            leave_room(f'classroom_{classroom_id}')

    @socketio.on('send_class_message')
    def on_send_class_message(data):
        """
        Flutter emits: { token: '...', classroomId: 5, body: 'Hello!' }
        Server saves to DB + broadcasts to classroom_5 room instantly.
        """
        token        = (data.get('token') or '').replace('Bearer ', '').strip()
        classroom_id = data.get('classroomId')
        body         = (data.get('body') or '').strip()

        user = _get_user_from_token(token)
        if not user or not classroom_id or not body:
            return
        if not _is_in_classroom(user.id, int(classroom_id)):
            return

        # Save to database
        result = db.session.execute(db.text("""
            INSERT INTO class_messages
                (classroom_id, sender_id, sender_name, sender_role, body)
            VALUES (:cid, :sid, :sname, :srole, :body)
        """), {
            'cid':   classroom_id,
            'sid':   user.id,
            'sname': user.name,
            'srole': user.role.value,
            'body':  body,
        })
        db.session.commit()

        msg_id     = result.lastrowid
        created_at = db.session.execute(
            db.text('SELECT created_at FROM class_messages WHERE id=:id'),
            {'id': msg_id}
        ).scalar()

        # Broadcast to everyone in the room
        payload = {
            'id':         msg_id,
            'senderId':   user.id,
            'senderName': user.name,
            'senderRole': user.role.value,
            'body':       body,
            'createdAt':  created_at.isoformat() if created_at else '',
        }
        emit('new_class_message', payload, room=f'classroom_{classroom_id}')

    # ── Direct message rooms ────────────────────────────────────────────────

    @socketio.on('join_dm')
    def on_join_dm(data):
        """
        Flutter emits: { token: '...', classroomId: 5, otherId: 12 }
        Room name is dm_{minId}_{maxId} so both users share the same room.
        """
        token        = (data.get('token') or '').replace('Bearer ', '').strip()
        classroom_id = data.get('classroomId')
        other_id     = data.get('otherId')

        user = _get_user_from_token(token)
        if not user or not classroom_id or not other_id:
            return
        if not _is_in_classroom(user.id, int(classroom_id)):
            return

        a, b = sorted([user.id, int(other_id)])
        room = f'dm_{a}_{b}'
        join_room(room)
        emit('joined', {'room': room})

    @socketio.on('leave_dm')
    def on_leave_dm(data):
        other_id = data.get('otherId')
        me_id    = data.get('myId')
        if other_id and me_id:
            a, b = sorted([int(me_id), int(other_id)])
            leave_room(f'dm_{a}_{b}')

    @socketio.on('send_dm')
    def on_send_dm(data):
        """
        Flutter emits: { token: '...', classroomId: 5, receiverId: 12, body: 'Hi' }
        Server saves + broadcasts to the shared DM room.
        """
        token       = (data.get('token') or '').replace('Bearer ', '').strip()
        classroom_id = data.get('classroomId')
        receiver_id  = data.get('receiverId')
        body         = (data.get('body') or '').strip()

        user = _get_user_from_token(token)
        if not user or not classroom_id or not receiver_id or not body:
            return
        if not _is_in_classroom(user.id, int(classroom_id)):
            return

        from models import User as UserModel
        receiver = UserModel.query.get(int(receiver_id))
        if not receiver:
            return

        # Save to database
        result = db.session.execute(db.text("""
            INSERT INTO direct_messages
                (classroom_id, sender_id, sender_name, sender_role,
                 receiver_id, receiver_name, body)
            VALUES (:cid, :sid, :sname, :srole, :rid, :rname, :body)
        """), {
            'cid':   classroom_id,
            'sid':   user.id,
            'sname': user.name,
            'srole': user.role.value,
            'rid':   receiver_id,
            'rname': receiver.name,
            'body':  body,
        })
        db.session.commit()

        msg_id     = result.lastrowid
        created_at = db.session.execute(
            db.text('SELECT created_at FROM direct_messages WHERE id=:id'),
            {'id': msg_id}
        ).scalar()

        a, b = sorted([user.id, int(receiver_id)])
        payload = {
            'id':         msg_id,
            'senderId':   user.id,
            'senderName': user.name,
            'senderRole': user.role.value,
            'body':       body,
            'createdAt':  created_at.isoformat() if created_at else '',
        }
        emit('new_dm', payload, room=f'dm_{a}_{b}')