"""Base repository for database operations."""

import logging
from app.extensions import db

logger = logging.getLogger(__name__)

class BaseRepository:
    """Base repository implementing common database operations."""
    
    def __init__(self, db_instance=None, model_class=None):
        """Initialize the repository.
        
        Args:
            db_instance: SQLAlchemy database instance
            model_class: Model class to use for queries
        """
        self.db = db_instance or db
        self.model_class = model_class
        
    def get_by_id(self, id):
        """Get an entity by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            Entity instance or None
        """
        if not self.model_class:
            raise NotImplementedError("Model class must be set in derived repository")
        
        return self.model_class.query.get(id)
        
    def get_all(self):
        """Get all entities.
        
        Returns:
            List of entities
        """
        if not self.model_class:
            raise NotImplementedError("Model class must be set in derived repository")
            
        return self.model_class.query.all()
    
    def save(self, entity):
        """Save an entity.
        
        Args:
            entity: Entity instance to save
            
        Returns:
            Entity instance
        """
        try:
            # Check if entity is already in session
            is_new = entity not in self.db.session
            
            if is_new:
                self.db.session.add(entity)
                
            self.db.session.commit()
            return entity
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error saving entity: {str(e)}")
            raise
    
    def delete(self, entity):
        """Delete an entity.
        
        Args:
            entity: Entity instance to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.db.session.delete(entity)
            self.db.session.commit()
            return True
        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error deleting entity: {str(e)}")
            raise
