from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.database.connection import get_db, ensure_auth_schema_compatibility
from app.models.auth_token import AuthToken
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.user_schema import (
    UserCreate, UserLogin, UserResponse,
    UserUpdate, UserProfile, ChangePasswordRequest
)
from app.core.auth_middleware import get_current_user
from app.services.email_service import send_welcome_email, send_password_reset_email, send_email_verification
from app.services.supabase_auth_service import (
    SupabaseAuthError,
    create_user_with_password,
    delete_user_by_id,
    get_oauth_authorize_url,
    get_user_from_access_token,
    sign_in_with_password,
    supabase_auth_enabled,
    supabase_password_auth_enabled,
    update_password as update_supabase_password,
)

from app.auth.password_hash import hash_password, verify_password
from app.auth.jwt_handler import create_access_token
from app.services.profile_service import ProfileService

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

logger = logging.getLogger("wallfruits_api")
bearer_security = HTTPBearer(auto_error=False)


def _normalize_role(role: str | None) -> str:
    if role in {"buyer", "producer", "admin"}:
        return role
    return "buyer"


def _login_response(db_user: User, access_token: str) -> dict:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "name": db_user.name,
            "email": db_user.email,
            "role": db_user.role,
            "profile_image": db_user.profile_image,
        }
    }


def _get_or_create_local_user_from_supabase(
    *,
    db: Session,
    supabase_user_id: str,
    email: str,
    fallback_name: str,
    fallback_role: str,
    plaintext_password: str,
) -> User:
    db_user = db.query(User).filter(User.supabase_user_id == supabase_user_id).first()
    if not db_user:
        db_user = db.query(User).filter(User.email == email).first()

    if db_user:
        if db_user.supabase_user_id and db_user.supabase_user_id != supabase_user_id:
            raise HTTPException(409, "Conflito de identidade entre usuário local e Supabase")

        changed = False
        if not db_user.supabase_user_id:
            db_user.supabase_user_id = supabase_user_id
            changed = True
        if changed:
            db.commit()
            db.refresh(db_user)
        return db_user

    db_user = User(
        name=fallback_name,
        email=email,
        password=hash_password(plaintext_password),
        role=_normalize_role(fallback_role),
        supabase_user_id=supabase_user_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def ensure_auth_schema_ready() -> None:
    """Garante que colunas novas da tabela users existam antes das consultas."""
    try:
        ensure_auth_schema_compatibility()
    except Exception as exc:
        logger.error(f"Erro ao sincronizar schema de auth: {exc}", exc_info=True)
        raise HTTPException(500, "Erro ao preparar banco de dados")


def _default_oauth_redirect_to(request: Request) -> str:
    """URL de retorno padrão do OAuth para a tela de login web."""
    return f"{str(request.base_url).rstrip('/')}/login"


# -----------------------
# GOOGLE LOGIN (SUPABASE OAUTH)
# -----------------------
@router.get("/google/login", include_in_schema=False)
def google_login_redirect(request: Request):
    """Redireciona para o login Google via Supabase Auth."""
    if not supabase_auth_enabled():
        raise HTTPException(400, "Login com Google indisponível. Habilite SUPABASE_AUTH_ENABLED.")

    try:
        oauth_url = get_oauth_authorize_url(
            provider="google",
            redirect_to=_default_oauth_redirect_to(request),
        )
    except SupabaseAuthError as exc:
        raise HTTPException(exc.status_code, exc.message)

    return RedirectResponse(url=oauth_url, status_code=status.HTTP_302_FOUND)


@router.post("/supabase/exchange")
def exchange_supabase_token(
    access_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Sincroniza usuário local a partir de um access_token do Supabase OAuth."""
    ensure_auth_schema_ready()

    if not supabase_auth_enabled():
        raise HTTPException(400, "Supabase Auth não está habilitado.")

    try:
        supabase_user = get_user_from_access_token(access_token)
    except SupabaseAuthError as exc:
        status_code = exc.status_code if exc.status_code >= 400 else 401
        raise HTTPException(status_code, exc.message)

    supabase_user_id = supabase_user.get("id")
    email = supabase_user.get("email")
    metadata = supabase_user.get("user_metadata") or {}

    if not supabase_user_id or not email:
        raise HTTPException(502, "Resposta de autenticação OAuth incompleta")

    try:
        db_user = _get_or_create_local_user_from_supabase(
            db=db,
            supabase_user_id=supabase_user_id,
            email=email,
            fallback_name=metadata.get("name") or email.split("@")[0],
            fallback_role=metadata.get("role") or "buyer",
            plaintext_password=supabase_user_id,
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Erro ao sincronizar usuário local com OAuth Google: %s", exc, exc_info=True)
        raise HTTPException(500, "Erro ao sincronizar usuário local")

    if not db_user.is_active:
        raise HTTPException(403, "Conta desativada")

    return _login_response(db_user, access_token)


# -----------------------
# REGISTER
# -----------------------
@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    ensure_auth_schema_ready()

    try:
        existing_user = db.query(User.id).filter(User.email == user.email).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao consultar email existente: {e}", exc_info=True)
        raise HTTPException(500, "Erro ao validar email no banco")

    if existing_user:
        raise HTTPException(400, "Email já cadastrado")

    if user.role == "admin":
        raise HTTPException(403, "Não é permitido registrar conta admin por esta rota")

    supabase_user_id: str | None = None
    if supabase_auth_enabled() and (settings.SUPABASE_ANON_KEY.strip() or settings.SUPABASE_SERVICE_ROLE_KEY.strip()):
        try:
            supabase_user = create_user_with_password(
                email=user.email,
                password=user.password,
                user_metadata={
                    "name": user.name,
                    "role": user.role,
                },
            )
            supabase_user_id = supabase_user.get("id")
            if not supabase_user_id:
                raise HTTPException(502, "Supabase Auth retornou usuario sem id")
        except SupabaseAuthError as exc:
            status_code = exc.status_code if exc.status_code >= 400 else 500
            raise HTTPException(status_code, exc.message)

    try:
        hashed_password = hash_password(user.password)
    except Exception as e:
        logger.error(f"Erro ao gerar hash da senha: {e}", exc_info=True)
        raise HTTPException(500, f"Erro ao processar senha: {type(e).__name__}")

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_password,
        supabase_user_id=supabase_user_id,
        role=user.role,
        phone=user.phone,
        location=user.location,
        bio=user.bio,
        profile_image=user.profile_image,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Fundação V1: toda conta nasce com um perfil ativo.
        try:
            ProfileService(db).bootstrap_profile_for_new_user(new_user)

            db.add(
                Subscription(
                    user_id=new_user.id,
                    plan_type="basic",
                    status="active",
                    auto_renew=True,
                )
            )
            db.commit()
        except Exception as profile_exc:
            logger.error("Falha ao criar perfil inicial do usuário: %s", profile_exc, exc_info=True)
            db.delete(new_user)
            db.commit()

            if supabase_user_id:
                try:
                    delete_user_by_id(supabase_user_id)
                except Exception as cleanup_exc:
                    logger.error("Falha ao remover usuário Supabase após erro de perfil: %s", cleanup_exc)

            raise HTTPException(500, "Erro ao criar perfil inicial da conta")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao salvar usuário no banco: {e}", exc_info=True)

        if supabase_user_id:
            try:
                delete_user_by_id(supabase_user_id)
                logger.warning("Usuário Supabase removido após falha no banco local")
            except Exception as cleanup_exc:
                logger.error("Falha ao remover usuário Supabase após rollback local: %s", cleanup_exc)

        raise HTTPException(500, f"Erro ao criar conta: {type(e).__name__}")

    # Enviar e-mail de boas-vindas (não-bloqueante)
    try:
        send_welcome_email(to=new_user.email, name=new_user.name)
    except Exception as email_exc:
        logger.warning("Falha ao enviar e-mail de boas-vindas: %s", email_exc)

    return new_user


# -----------------------
# LOGIN
# -----------------------
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    ensure_auth_schema_ready()

    if supabase_password_auth_enabled():
        try:
            auth_data = sign_in_with_password(user.email, user.password)
        except SupabaseAuthError as exc:
            if exc.status_code in {400, 401, 422}:
                raise HTTPException(401, "Credenciais inválidas")
            raise HTTPException(exc.status_code, exc.message)

        access_token = auth_data.get("access_token")
        supabase_user = auth_data.get("user") or {}
        supabase_user_id = supabase_user.get("id")
        email = supabase_user.get("email") or user.email
        metadata = supabase_user.get("user_metadata") or {}

        if not access_token or not supabase_user_id or not email:
            raise HTTPException(502, "Resposta de login do Supabase incompleta")

        try:
            db_user = _get_or_create_local_user_from_supabase(
                db=db,
                supabase_user_id=supabase_user_id,
                email=email,
                fallback_name=metadata.get("name") or email.split("@")[0],
                fallback_role=metadata.get("role") or "buyer",
                plaintext_password=user.password,
            )
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Erro ao sincronizar usuario local com Supabase: {e}", exc_info=True)
            raise HTTPException(500, "Erro ao sincronizar usuário local")

        if not db_user.is_active:
            raise HTTPException(403, "Conta desativada")

        return _login_response(db_user, access_token)

    try:
        db_user = db.query(User).filter(User.email == user.email).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao consultar usuario para login: {e}", exc_info=True)
        raise HTTPException(500, "Erro ao consultar usuário no banco")

    if not db_user:
        raise HTTPException(401, "Credenciais inválidas")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(401, "Credenciais inválidas")

    if not db_user.is_active:
        raise HTTPException(403, "Conta desativada")

    token = create_access_token({
        "user_id": db_user.id,
        "email": db_user.email,
        "role": db_user.role
    })

    return _login_response(db_user, token)


# -----------------------
# GET CURRENT USER PROFILE
# -----------------------
@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

    # Calcular estatísticas
    from sqlalchemy import and_, func, or_
    from app.models import Offer, Transaction, Favorite, Message

    profile_service = ProfileService(db)
    current_profile = profile_service.get_or_create_profile(current_user)

    owner_filter = or_(
        Offer.owner_profile_id == current_profile.id,
        and_(Offer.owner_profile_id.is_(None), Offer.user_id == current_user.id),
    )

    # Total de ofertas
    total_offers = db.query(func.count(Offer.id)).filter(owner_filter).scalar()

    # Total de vendas (transações como vendedor)
    total_sales = db.query(func.count(Transaction.id)).join(Offer).filter(owner_filter).scalar()

    # Total de compras
    total_purchases = db.query(func.count(Transaction.id)).filter(Transaction.buyer_id == current_user.id).scalar()

    # Total de favoritos
    favorite_count = db.query(func.count(Favorite.id)).filter(Favorite.user_id == current_user.id).scalar()

    # Mensagens não lidas
    unread_messages = db.query(func.count(Message.id)).filter(
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).scalar()

    profile_data = {
        **current_user.__dict__,
        "total_offers": total_offers,
        "total_sales": total_sales,
        "total_purchases": total_purchases,
        "favorite_count": favorite_count,
        "unread_messages": unread_messages
    }

    return profile_data


# -----------------------
# UPDATE USER PROFILE
# -----------------------
@router.put("/me", response_model=UserResponse)
def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user


# -----------------------
# CHANGE PASSWORD
# -----------------------
@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest | None = Body(default=None),
    current_password: str | None = None,
    new_password: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resolved_current_password = payload.current_password if payload else current_password
    resolved_new_password = payload.new_password if payload else new_password

    if not resolved_new_password:
        raise HTTPException(422, "Informe a nova senha")

    if not resolved_current_password and not (supabase_auth_enabled() and credentials):
        raise HTTPException(422, "Informe a senha atual")

    if len(resolved_new_password) < 6:
        raise HTTPException(400, "Nova senha deve ter pelo menos 6 caracteres")

    if supabase_auth_enabled() and credentials:
        try:
            update_supabase_password(credentials.credentials, resolved_new_password)
        except SupabaseAuthError as exc:
            if exc.status_code in {400, 401, 403}:
                raise HTTPException(401, "Token inválido para alterar senha no Supabase")
            raise HTTPException(exc.status_code, exc.message)
    else:
        if not verify_password(str(resolved_current_password), current_user.password):
            raise HTTPException(400, "Senha atual incorreta")

    current_user.password = hash_password(resolved_new_password)
    db.commit()

    return {"message": "Senha alterada com sucesso"}


# -----------------------
# FORGOT PASSWORD
# -----------------------
@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(email: str = Body(..., embed=True), db: Session = Depends(get_db)):
    """Envia link de reset de senha por e-mail."""
    # Sempre retorna 200 para não revelar se o e-mail existe (segurança)
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user:
        return {"message": "Se o e-mail estiver cadastrado, você receberá as instruções."}

    token_obj = AuthToken.new_reset(user.id)
    db.add(token_obj)
    db.commit()

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token_obj.token}"
    send_password_reset_email(to=user.email, name=user.name, reset_url=reset_url)

    return {"message": "Se o e-mail estiver cadastrado, você receberá as instruções."}


# -----------------------
# RESET PASSWORD (com token)
# -----------------------
@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    token: str = Body(...),
    new_password: str = Body(..., min_length=6),
    db: Session = Depends(get_db),
):
    """Redefine a senha usando o token recebido por e-mail."""
    token_obj = (
        db.query(AuthToken)
        .filter(AuthToken.token == token, AuthToken.token_type == "password_reset")
        .first()
    )
    if not token_obj or not token_obj.is_valid():
        raise HTTPException(400, "Token inválido ou expirado.")

    user = db.query(User).filter(User.id == token_obj.user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")

    user.password = hash_password(new_password)
    token_obj.used = True
    db.commit()

    return {"message": "Senha redefinida com sucesso. Faça login com a nova senha."}


# -----------------------
# VERIFY EMAIL
# -----------------------
@router.post("/send-verification", status_code=status.HTTP_200_OK)
def send_verification_email(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reenviar e-mail de verificação."""
    if current_user.is_verified:
        return {"message": "E-mail já verificado."}

    token_obj = AuthToken.new_verify(current_user.id)
    db.add(token_obj)
    db.commit()

    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token_obj.token}"
    send_email_verification(to=current_user.email, name=current_user.name, verify_url=verify_url)

    return {"message": "E-mail de verificação enviado."}


@router.get("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(token: str, db: Session = Depends(get_db)):
    """Confirma o e-mail via token."""
    token_obj = (
        db.query(AuthToken)
        .filter(AuthToken.token == token, AuthToken.token_type == "email_verify")
        .first()
    )
    if not token_obj or not token_obj.is_valid():
        raise HTTPException(400, "Token inválido ou expirado.")

    user = db.query(User).filter(User.id == token_obj.user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")

    user.is_verified = True
    token_obj.used = True
    db.commit()

    return {"message": "E-mail verificado com sucesso."}