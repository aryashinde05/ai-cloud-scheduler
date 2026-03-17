from datetime import datetime
import os
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode

from app.database.session import Base

# Using generic SECRET_KEY if specific one is missing
fernet_key_str = os.getenv("AWS_CREDENTIAL_SECRET_KEY", os.getenv("SECRET_KEY", "default-insecure-key-for-dev-only"))

def _get_fernet() -> Fernet:
    key = fernet_key_str.encode("utf-8")
    # Ensure key is valid length by deriving/padding
    padded = key.ljust(32, b"0")[:32]
    return Fernet(urlsafe_b64encode(padded))


class AwsAccount(Base):
    __tablename__ = "aws_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="default", unique=True, index=True)
    access_key_encrypted = Column(String(512), nullable=False)
    secret_key_encrypted = Column(String(512), nullable=False)
    region = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    @staticmethod
    def _encrypt(value: str) -> str:
        f = _get_fernet()
        return f.encrypt(value.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _decrypt(value: str) -> str:
        f = _get_fernet()
        return f.decrypt(value.encode("utf-8")).decode("utf-8")

    def get_decrypted_credentials(self):
        return (
            self._decrypt(self.access_key_encrypted),
            self._decrypt(self.secret_key_encrypted),
            self.region,
        )

    @classmethod
    def get_default(cls, db: Session) -> "AwsAccount":
        return db.query(cls).filter(cls.name == "default").first()

    @classmethod
    def create_or_update_default(
        cls,
        db: Session,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> "AwsAccount":
        account = db.query(cls).filter(cls.name == "default").first()
        if not account:
            account = cls(name="default")
            db.add(account)
        
        # Always update credentials/region
        account.access_key_encrypted = cls._encrypt(access_key)
        account.secret_key_encrypted = cls._encrypt(secret_key)
        account.region = region
        account.is_active = True
        
        db.commit()
        db.refresh(account)
        return account
