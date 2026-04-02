from pathlib import Path
import sys

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import SessionLocal, engine
from app.models import CommunityComment, CommunityLike, CommunityPost, CommunityShare


def main() -> None:
    try:
        inspector = inspect(engine)
        names = set(inspector.get_table_names())
    except SQLAlchemyError as exc:
        print("connection_error=", str(exc))
        return

    required = {"community_posts", "community_comments", "community_likes", "community_shares"}
    missing = sorted(required - names)

    print("tables_found=", sorted(required & names))
    print("tables_missing=", missing)

    if missing:
        print("skip_delete_due_to_missing_tables")
        return

    session = SessionLocal()
    try:
        deleted_comments = session.query(CommunityComment).delete(synchronize_session=False)
        deleted_likes = session.query(CommunityLike).delete(synchronize_session=False)
        deleted_shares = session.query(CommunityShare).delete(synchronize_session=False)
        deleted_posts = session.query(CommunityPost).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    print(
        {
            "deleted_posts": int(deleted_posts or 0),
            "deleted_comments": int(deleted_comments or 0),
            "deleted_likes": int(deleted_likes or 0),
            "deleted_shares": int(deleted_shares or 0),
        }
    )


if __name__ == "__main__":
    main()
