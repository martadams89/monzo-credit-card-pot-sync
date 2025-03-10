from app.models.user import User
from app.extensions import login_manager
from app.models.user_repository import SqlAlchemyUserRepository
from app.extensions import db

user_repository = SqlAlchemyUserRepository(db)

@login_manager.user_loader
def load_user(user_id):
    """Load user from database."""
    return user_repository.get_by_id(user_id)
