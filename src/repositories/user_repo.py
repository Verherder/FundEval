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

    def is_admin(self, user_id):
        return self._db.is_admin(user_id)

    def create_invitation(self, token_hash, created_by, expires_at):
        return self._db.create_invitation(token_hash, created_by, expires_at)

    def invitation_is_valid(self, token_hash):
        return self._db.invitation_is_valid(token_hash)

    def consume_invitation(self, token_hash, user_id):
        return self._db.consume_invitation(token_hash, user_id)

    def save_remember_token(self, user_id, token_hash, expires_at):
        return self._db.save_remember_token(user_id, token_hash, expires_at)

    def consume_remember_token(self, token_hash):
        return self._db.consume_remember_token(token_hash)

    def revoke_remember_tokens(self, user_id):
        return self._db.revoke_remember_tokens(user_id)

    def login_is_limited(self, identity_hash):
        return self._db.login_is_limited(identity_hash)

    def record_login_attempt(self, identity_hash, succeeded):
        return self._db.record_login_attempt(identity_hash, succeeded)

    def reset_password(self, username, password):
        return self._db.reset_password(username, password)
