# -*- coding: UTF-8 -*-
"""User repository — manages users table operations."""

from loguru import logger


class UserRepo:
    """Repository for user-related database operations."""

    def __init__(self, db):
        """Initialize with a Database instance.

        Args:
            db: Database instance with get_connection() method.
        """
        self._db = db

    def create_user(self, username, password):
        """Create a new user.

        Args:
            username: Username.
            password: Plaintext password.

        Returns:
            (success: bool, message: str, user_id: int or None)
        """
        return self._db.create_user(username, password)

    def get_user_by_username(self, username):
        """Get user info by username.

        Returns:
            dict or None
        """
        return self._db.get_user_by_username(username)

    def verify_password(self, username, password):
        """Verify user password.

        Returns:
            (success: bool, user_id: int or None)
        """
        return self._db.verify_password(username, password)
