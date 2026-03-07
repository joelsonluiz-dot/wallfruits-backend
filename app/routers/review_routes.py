from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.connection import get_db
from app.models import Review, Transaction, User
from app.schemas import ReviewCreate, ReviewUpdate, ReviewResponse, ReviewStats
from app.core.auth_middleware import get_current_user

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"]
)


# -----------------------------
# CREATE REVIEW
# -----------------------------
@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    review: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Verificar se a transação existe e o usuário participou dela
    transaction = db.query(Transaction).filter(Transaction.id == review.transaction_id).first()

    if not transaction:
        raise HTTPException(404, "Transação não encontrada")

    # Verificar se o usuário é o comprador
    if transaction.buyer_id != current_user.id:
        raise HTTPException(403, "Apenas o comprador pode avaliar esta transação")

    # Verificar se já existe avaliação para esta transação
    existing_review = db.query(Review).filter(
        Review.transaction_id == review.transaction_id,
        Review.reviewer_id == current_user.id
    ).first()

    if existing_review:
        raise HTTPException(400, "Você já avaliou esta transação")

    # Verificar se a transação está concluída
    if transaction.status != "completed":
        raise HTTPException(400, "Apenas transações concluídas podem ser avaliadas")

    # Criar avaliação
    new_review = Review(
        reviewer_id=current_user.id,
        reviewed_user_id=review.reviewed_user_id,
        offer_id=review.offer_id,
        transaction_id=review.transaction_id,
        rating=review.rating,
        title=review.title,
        comment=review.comment,
        review_type=review.review_type,
        is_verified=True  # Avaliação após transação real
    )

    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    # Atualizar rating do usuário avaliado
    reviewed_user = db.query(User).filter(User.id == review.reviewed_user_id).first()
    if reviewed_user:
        # Recalcular rating médio
        from sqlalchemy import func
        rating_stats = db.query(
            func.avg(Review.rating),
            func.count(Review.id)
        ).filter(Review.reviewed_user_id == review.reviewed_user_id).one()

        reviewed_user.rating = int(rating_stats[0] or 0)
        reviewed_user.total_reviews = rating_stats[1]
        db.commit()

    return new_review


# -----------------------------
# GET USER REVIEWS
# -----------------------------
@router.get("/user/{user_id}", response_model=List[ReviewResponse])
def get_user_reviews(
    user_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):

    reviews = db.query(Review).filter(
        Review.reviewed_user_id == user_id
    ).order_by(Review.created_at.desc()).offset(skip).limit(limit).all()

    return reviews


# -----------------------------
# GET USER REVIEW STATS
# -----------------------------
@router.get("/user/{user_id}/stats", response_model=ReviewStats)
def get_user_review_stats(user_id: int, db: Session = Depends(get_db)):

    from sqlalchemy import func

    # Estatísticas gerais
    stats = db.query(
        func.avg(Review.rating),
        func.count(Review.id)
    ).filter(Review.reviewed_user_id == user_id).one()

    # Distribuição de ratings
    rating_dist = db.query(
        Review.rating,
        func.count(Review.id)
    ).filter(Review.reviewed_user_id == user_id).group_by(Review.rating).all()

    distribution = {i: 0 for i in range(1, 6)}
    for rating, count in rating_dist:
        distribution[rating] = count

    # Reviews verificadas
    verified_count = db.query(func.count(Review.id)).filter(
        Review.reviewed_user_id == user_id,
        Review.is_verified == True
    ).scalar()

    return ReviewStats(
        average_rating=float(stats[0] or 0),
        total_reviews=stats[1],
        rating_distribution=distribution,
        verified_reviews=verified_count
    )


# -----------------------------
# UPDATE REVIEW (APENAS O AUTOR)
# -----------------------------
@router.put("/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: UUID,
    review_update: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    review = db.query(Review).filter(Review.id == review_id).first()

    if not review:
        raise HTTPException(404, "Avaliação não encontrada")

    if review.reviewer_id != current_user.id:
        raise HTTPException(403, "Apenas o autor pode editar a avaliação")

    # Atualizar campos
    for field, value in review_update.dict(exclude_unset=True).items():
        setattr(review, field, value)

    db.commit()
    db.refresh(review)

    return review


# -----------------------------
# RESPONDER REVIEW (APENAS AVALIADO)
# -----------------------------
@router.post("/{review_id}/response")
def respond_to_review(
    review_id: UUID,
    response: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    review = db.query(Review).filter(Review.id == review_id).first()

    if not review:
        raise HTTPException(404, "Avaliação não encontrada")

    if review.reviewed_user_id != current_user.id:
        raise HTTPException(403, "Apenas o usuário avaliado pode responder")

    if review.response:
        raise HTTPException(400, "Esta avaliação já foi respondida")

    review.response = response
    review.response_date = func.now()

    db.commit()

    return {"message": "Resposta enviada com sucesso"}