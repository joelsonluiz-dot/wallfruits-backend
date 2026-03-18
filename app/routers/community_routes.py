from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user, get_current_user_optional
from app.database.connection import get_db
from app.models import CommunityComment, CommunityLike, CommunityPost, CommunityShare, CommunityUserBlock, User
from app.schemas.community_schema import (
    CommunityBlockUserRequest,
    CommunityCommentCreate,
    CommunityCommentResponse,
    CommunityLikeToggleResponse,
    CommunityModerationActionResponse,
    CommunityPostCreate,
    CommunityPostListResponse,
    CommunityPostResponse,
    CommunityShareResponse,
)
from app.services.notification_service import create_notification

router = APIRouter(prefix="/community", tags=["community"])


def _normalize_profile_image(image: str | None) -> str | None:
    if not image:
        return None
    if image.startswith("http://") or image.startswith("https://") or image.startswith("/"):
        return image
    return f"/api/uploads/profiles/{image}"


def _author_payload(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "profile_image": _normalize_profile_image(user.profile_image),
    }


def _build_post_response(post: CommunityPost, likes_count: int, comments_count: int, shares_count: int, liked_by_me: bool) -> CommunityPostResponse:
    return CommunityPostResponse(
        id=post.id,
        content=post.content or "",
        image_url=post.image_url,
        created_at=post.created_at,
        author=_author_payload(post.user),
        likes_count=int(likes_count or 0),
        comments_count=int(comments_count or 0),
        shares_count=int(shares_count or 0),
        liked_by_me=bool(liked_by_me),
    )


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _require_admin(user: User) -> None:
    if not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito para admin")


def _assert_user_not_blocked(db: Session, user_id: int) -> None:
    blocked = (
        db.query(CommunityUserBlock)
        .filter(CommunityUserBlock.user_id == user_id, CommunityUserBlock.is_active.is_(True))
        .first()
    )
    if blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário bloqueado para interações na comunidade")


@router.get("/posts", response_model=CommunityPostListResponse)
def list_posts(
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    post_id: int | None = Query(None, ge=1),
):
    likes_subq = (
        db.query(CommunityLike.post_id.label("post_id"), func.count(CommunityLike.id).label("likes_count"))
        .group_by(CommunityLike.post_id)
        .subquery()
    )

    comments_subq = (
        db.query(CommunityComment.post_id.label("post_id"), func.count(CommunityComment.id).label("comments_count"))
        .filter(CommunityComment.is_active.is_(True))
        .group_by(CommunityComment.post_id)
        .subquery()
    )

    shares_subq = (
        db.query(CommunityShare.post_id.label("post_id"), func.count(CommunityShare.id).label("shares_count"))
        .group_by(CommunityShare.post_id)
        .subquery()
    )

    liked_by_me_expr = func.coalesce(func.max(case((CommunityLike.user_id == (current_user.id if current_user else -1), 1), else_=0)), 0)

    base_query = (
        db.query(
            CommunityPost,
            func.coalesce(likes_subq.c.likes_count, 0).label("likes_count"),
            func.coalesce(comments_subq.c.comments_count, 0).label("comments_count"),
            func.coalesce(shares_subq.c.shares_count, 0).label("shares_count"),
            liked_by_me_expr.label("liked_by_me"),
        )
        .join(User, User.id == CommunityPost.user_id)
        .outerjoin(likes_subq, likes_subq.c.post_id == CommunityPost.id)
        .outerjoin(comments_subq, comments_subq.c.post_id == CommunityPost.id)
        .outerjoin(shares_subq, shares_subq.c.post_id == CommunityPost.id)
        .outerjoin(CommunityLike, CommunityLike.post_id == CommunityPost.id)
        .filter(CommunityPost.is_active.is_(True))
        .group_by(CommunityPost.id, likes_subq.c.likes_count, comments_subq.c.comments_count, shares_subq.c.shares_count)
        .order_by(CommunityPost.created_at.desc())
    )

    if post_id:
        base_query = base_query.filter(CommunityPost.id == post_id)

    rows = (
        base_query
        .offset(skip)
        .limit(limit)
        .all()
    )

    total_query = db.query(func.count(CommunityPost.id)).filter(CommunityPost.is_active.is_(True))
    if post_id:
        total_query = total_query.filter(CommunityPost.id == post_id)
    total = total_query.scalar() or 0

    payload = [
        _build_post_response(post, likes_count, comments_count, shares_count, bool(liked_by_me))
        for post, likes_count, comments_count, shares_count, liked_by_me in rows
    ]

    return CommunityPostListResponse(posts=payload, total=int(total))


@router.get("/posts/{post_id}", response_model=CommunityPostResponse)
def get_post(
    post_id: int,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    data = list_posts(current_user=current_user, db=db, skip=0, limit=1, post_id=post_id)
    if not data.posts:
        raise HTTPException(status_code=404, detail="Post não encontrado")
    return data.posts[0]


@router.post("/posts", response_model=CommunityPostResponse)
def create_post(
    body: CommunityPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_user_not_blocked(db, current_user.id)

    if not body.content and not body.image_url:
        raise HTTPException(status_code=400, detail="Informe texto ou imagem para publicar")

    row = CommunityPost(
        user_id=current_user.id,
        content=body.content or "",
        image_url=body.image_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return _build_post_response(row, 0, 0, 0, False)


@router.get("/posts/{post_id}/comments", response_model=list[CommunityCommentResponse])
def list_post_comments(
    post_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    post_exists = (
        db.query(CommunityPost.id)
        .filter(CommunityPost.id == post_id, CommunityPost.is_active.is_(True))
        .first()
    )
    if not post_exists:
        raise HTTPException(status_code=404, detail="Post não encontrado")

    rows = (
        db.query(CommunityComment)
        .join(User, User.id == CommunityComment.user_id)
        .filter(
            CommunityComment.post_id == post_id,
            CommunityComment.is_active.is_(True),
        )
        .order_by(CommunityComment.created_at.asc())
        .limit(limit)
        .all()
    )

    return [
        CommunityCommentResponse(
            id=item.id,
            post_id=item.post_id,
            content=item.content,
            created_at=item.created_at,
            author=_author_payload(item.user),
        )
        for item in rows
    ]


@router.post("/posts/{post_id}/comments", response_model=CommunityCommentResponse)
def create_comment(
    post_id: int,
    body: CommunityCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_user_not_blocked(db, current_user.id)

    post = (
        db.query(CommunityPost)
        .filter(CommunityPost.id == post_id, CommunityPost.is_active.is_(True))
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado")

    row = CommunityComment(
        post_id=post.id,
        user_id=current_user.id,
        content=body.content,
    )
    db.add(row)

    if post.user_id != current_user.id:
        create_notification(
            db,
            user_id=post.user_id,
            actor_user_id=current_user.id,
            notification_type="community_comment",
            title="Novo comentário",
            message=f"{current_user.name} comentou no seu post.",
            resource_type="community_post",
            resource_id=str(post.id),
        )

    db.commit()
    db.refresh(row)

    return CommunityCommentResponse(
        id=row.id,
        post_id=row.post_id,
        content=row.content,
        created_at=row.created_at,
        author=_author_payload(current_user),
    )


@router.post("/posts/{post_id}/like", response_model=CommunityLikeToggleResponse)
def toggle_like_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_user_not_blocked(db, current_user.id)

    post = (
        db.query(CommunityPost)
        .filter(CommunityPost.id == post_id, CommunityPost.is_active.is_(True))
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado")

    like = (
        db.query(CommunityLike)
        .filter(CommunityLike.post_id == post.id, CommunityLike.user_id == current_user.id)
        .first()
    )

    liked = False
    if like:
        db.delete(like)
    else:
        db.add(CommunityLike(post_id=post.id, user_id=current_user.id))
        liked = True

        if post.user_id != current_user.id:
            create_notification(
                db,
                user_id=post.user_id,
                actor_user_id=current_user.id,
                notification_type="community_like",
                title="Seu post recebeu uma curtida",
                message=f"{current_user.name} curtiu seu post.",
                resource_type="community_post",
                resource_id=str(post.id),
            )

    db.commit()

    likes_count = (
        db.query(func.count(CommunityLike.id))
        .filter(CommunityLike.post_id == post.id)
        .scalar()
        or 0
    )

    return CommunityLikeToggleResponse(success=True, liked=liked, likes_count=int(likes_count))


@router.post("/posts/{post_id}/share", response_model=CommunityShareResponse)
def share_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_user_not_blocked(db, current_user.id)

    post = (
        db.query(CommunityPost)
        .filter(CommunityPost.id == post_id, CommunityPost.is_active.is_(True))
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado")

    existing_share = (
        db.query(CommunityShare)
        .filter(CommunityShare.post_id == post.id, CommunityShare.user_id == current_user.id)
        .first()
    )
    is_new_share = existing_share is None
    if is_new_share:
        db.add(CommunityShare(post_id=post.id, user_id=current_user.id))

    if is_new_share and post.user_id != current_user.id:
        create_notification(
            db,
            user_id=post.user_id,
            actor_user_id=current_user.id,
            notification_type="community_share",
            title="Seu post foi compartilhado",
            message=f"{current_user.name} compartilhou seu post.",
            resource_type="community_post",
            resource_id=str(post.id),
        )

    db.commit()

    shares_count = (
        db.query(func.count(CommunityShare.id))
        .filter(
            CommunityShare.post_id == post.id,
        )
        .scalar()
        or 0
    )

    share_url = str(request.base_url).rstrip("/") + f"/community?post={post.id}"
    return CommunityShareResponse(success=True, shares_count=int(shares_count), share_url=share_url)


@router.post("/moderation/posts/{post_id}/hide", response_model=CommunityModerationActionResponse)
def moderate_hide_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    row = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Post não encontrado")

    row.is_active = False
    db.commit()
    return CommunityModerationActionResponse(success=True, action="hide", target_type="post", target_id=post_id)


@router.delete("/moderation/posts/{post_id}", response_model=CommunityModerationActionResponse)
def moderate_remove_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    row = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Post não encontrado")

    db.delete(row)
    db.commit()
    return CommunityModerationActionResponse(success=True, action="remove", target_type="post", target_id=post_id)


@router.post("/moderation/comments/{comment_id}/hide", response_model=CommunityModerationActionResponse)
def moderate_hide_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    row = db.query(CommunityComment).filter(CommunityComment.id == comment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Comentário não encontrado")

    row.is_active = False
    db.commit()
    return CommunityModerationActionResponse(success=True, action="hide", target_type="comment", target_id=comment_id)


@router.delete("/moderation/comments/{comment_id}", response_model=CommunityModerationActionResponse)
def moderate_remove_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    row = db.query(CommunityComment).filter(CommunityComment.id == comment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Comentário não encontrado")

    db.delete(row)
    db.commit()
    return CommunityModerationActionResponse(success=True, action="remove", target_type="comment", target_id=comment_id)


@router.post("/moderation/users/{user_id}/block", response_model=CommunityModerationActionResponse)
def moderate_block_user(
    user_id: int,
    body: CommunityBlockUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode bloquear a si mesmo")

    user_exists = db.query(User.id).filter(User.id == user_id).first()
    if not user_exists:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    row = db.query(CommunityUserBlock).filter(CommunityUserBlock.user_id == user_id).first()
    if row:
        row.is_active = True
        row.blocked_by_user_id = current_user.id
        row.reason = body.reason
    else:
        db.add(
            CommunityUserBlock(
                user_id=user_id,
                blocked_by_user_id=current_user.id,
                reason=body.reason,
                is_active=True,
            )
        )

    db.commit()
    return CommunityModerationActionResponse(success=True, action="block", target_type="user", target_id=user_id)
