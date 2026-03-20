from fastapi import APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database.connection import get_db, SessionLocal
from app.models import Message, User, Offer
from app.schemas import MessageCreate, MessageResponse, ConversationResponse
from app.core.auth_middleware import get_current_user, get_user_from_token
from app.services.notification_service import create_notification

router = APIRouter(
    prefix="/messages",
    tags=["messages"]
)

# Manager para conexões WebSocket de chat
class ChatManager:
    def __init__(self):
        self.active_connections: dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            connections = self.active_connections[user_id]
            if websocket in connections:
                connections.remove(websocket)
            if not connections:
                del self.active_connections[user_id]

    async def send_message(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for websocket in list(self.active_connections[user_id]):
                try:
                    await websocket.send_json(message)
                except Exception:
                    self.disconnect(user_id, websocket)

chat_manager = ChatManager()


# -----------------------------
# SEND MESSAGE
# -----------------------------
@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enviar mensagem para outro usuário"""
    try:
        # Verificar se o destinatário existe
        receiver = db.query(User).filter(User.id == message.receiver_id).first()
        if not receiver:
            raise HTTPException(404, "Destinatário não encontrado")
        
        # Não permitir enviar mensagem para si mesmo
        if message.receiver_id == current_user.id:
            raise HTTPException(400, "Não é possível enviar mensagem para você mesmo")

        # Se for sobre uma oferta, verificar se ela existe
        if message.offer_id:
            offer = db.query(Offer).filter(Offer.id == message.offer_id).first()
            if not offer:
                raise HTTPException(404, "Oferta não encontrada")

        # Criar thread_id se não fornecido
        thread_id = message.thread_id
        if not thread_id:
            # Criar novo thread baseado nos usuários e oferta
            import hashlib
            thread_str = f"{min(current_user.id, message.receiver_id)}-{max(current_user.id, message.receiver_id)}-{message.offer_id or 'general'}"
            thread_hash = hashlib.md5(thread_str.encode()).hexdigest()
            thread_id = UUID(f"{thread_hash[:8]}-{thread_hash[8:12]}-{thread_hash[12:16]}-{thread_hash[16:20]}-{thread_hash[20:32]}")

        # Criar mensagem
        new_message = Message(
            sender_id=current_user.id,
            receiver_id=message.receiver_id,
            offer_id=message.offer_id,
            subject=message.subject,
            content=message.content,
            message_type=message.message_type,
            thread_id=thread_id
        )

        db.add(new_message)

        notification_title = "Nova mensagem"
        notification_text = f"{current_user.name} enviou uma mensagem para você."
        if message.message_type == "offer_inquiry" and message.offer_id:
            notification_title = "Novo interesse em oferta"
            product_name = offer.product_name if message.offer_id and offer else "sua oferta"
            notification_text = f"{current_user.name} demonstrou interesse em {product_name}."

        create_notification(
            db,
            user_id=message.receiver_id,
            actor_user_id=current_user.id,
            notification_type="message",
            title=notification_title,
            message=notification_text,
            resource_type="thread",
            resource_id=str(thread_id),
        )

        db.commit()
        db.refresh(new_message)

        await chat_manager.send_message(
            message.receiver_id,
            {
                "event": "new_message",
                "thread_id": str(new_message.thread_id),
                "message": {
                    "id": str(new_message.id),
                    "sender_id": new_message.sender_id,
                    "receiver_id": new_message.receiver_id,
                    "offer_id": str(new_message.offer_id) if new_message.offer_id else None,
                    "subject": new_message.subject,
                    "content": new_message.content,
                    "message_type": new_message.message_type,
                    "created_at": new_message.created_at.isoformat()
                }
            }
        )

        return new_message
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erro ao enviar mensagem: {str(e)}")


# -----------------------------
# GET MY MESSAGES
# -----------------------------
@router.get("", response_model=List[MessageResponse])
@router.get("/", response_model=List[MessageResponse])
def get_my_messages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50
):

    query = db.query(Message).filter(
        (Message.sender_id == current_user.id) |
        (Message.receiver_id == current_user.id)
    )

    if unread_only:
        query = query.filter(
            Message.receiver_id == current_user.id,
            Message.is_read == False
        )

    messages = query.order_by(Message.created_at.desc()).offset(skip).limit(limit).all()

    return messages


# -----------------------------
# GET CONVERSATIONS
# -----------------------------
@router.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Buscar threads únicos onde o usuário participa
    from sqlalchemy import func, distinct

    threads = db.query(
        Message.thread_id,
        func.max(Message.created_at).label('last_message_time')
    ).filter(
        (Message.sender_id == current_user.id) |
        (Message.receiver_id == current_user.id)
    ).group_by(Message.thread_id).order_by(func.max(Message.created_at).desc()).all()

    conversations = []

    for thread_id, last_time in threads:
        # Buscar última mensagem do thread
        last_message = db.query(Message).filter(
            Message.thread_id == thread_id
        ).order_by(Message.created_at.desc()).first()

        if last_message:
            # Determinar o outro usuário
            other_user_id = (last_message.receiver_id
                           if last_message.sender_id == current_user.id
                           else last_message.sender_id)

            other_user = db.query(User).filter(User.id == other_user_id).first()

            # Contar mensagens não lidas
            unread_count = db.query(func.count(Message.id)).filter(
                Message.thread_id == thread_id,
                Message.receiver_id == current_user.id,
                Message.is_read == False
            ).scalar()

            conversations.append(ConversationResponse(
                thread_id=thread_id,
                other_user={
                    "id": other_user.id,
                    "name": other_user.name,
                    "profile_image": other_user.profile_image
                },
                last_message=MessageResponse.from_orm(last_message),
                unread_count=unread_count,
                total_messages=db.query(func.count(Message.id)).filter(
                    Message.thread_id == thread_id
                ).scalar(),
                updated_at=last_time
            ))

    return conversations


# -----------------------------
# GET THREAD MESSAGES
# -----------------------------
@router.get("/thread/{thread_id}", response_model=List[MessageResponse])
def get_thread_messages(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    mark_as_read: bool = True
):

    # Verificar se o usuário participa do thread
    thread_messages = db.query(Message).filter(
        Message.thread_id == thread_id,
        ((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()

    if not thread_messages:
        raise HTTPException(404, "Thread não encontrado ou acesso negado")

    # Marcar mensagens como lidas
    if mark_as_read:
        db.query(Message).filter(
            Message.thread_id == thread_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).update({"is_read": True})
        db.commit()

    return thread_messages


# -----------------------------
# MARK MESSAGES AS READ
# -----------------------------
@router.put("/read/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def mark_thread_as_read(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Verificar se o usuário participa do thread
    thread_exists = db.query(Message).filter(
        Message.thread_id == thread_id,
        ((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id))
    ).first()

    if not thread_exists:
        raise HTTPException(404, "Thread não encontrado")

    # Marcar como lidas
    db.query(Message).filter(
        Message.thread_id == thread_id,
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).update({"is_read": True})

    db.commit()


# -----------------------------
# WEBSOCKET CHAT
# -----------------------------
@router.websocket("/ws/{user_id}")
async def chat_websocket(
    user_id: int,
    websocket: WebSocket,
    token: str
):
    db = SessionLocal()

    try:
        current_user = get_user_from_token(token, db)
        if user_id != current_user.id:
            await websocket.close(code=1008)
            return

        await chat_manager.connect(user_id, websocket)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chat_manager.disconnect(user_id, websocket)
    except HTTPException:
        await websocket.close(code=1008)
    finally:
        db.close()