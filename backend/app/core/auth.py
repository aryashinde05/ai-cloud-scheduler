"""
JWT Authentication and Authorization system for FinOps Platform
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.services.startup_migration.models import User, UserRole
from app.services.repositories import UserRepository
from app.database.database import get_db_session
from sqlalchemy.orm import Session

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme - auto_error=False makes credentials optional
security = HTTPBearer(auto_error=False)

class TokenPayload(BaseModel):
    """JWT token payload structure"""
    sub: str  # user_id
    email: str
    role: str
    exp: int
    iat: int
    type: str  # 'access' or 'refresh'

class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthenticationService:
    """JWT-based authentication service"""
    
    def __init__(self):
        self.secret_key = JWT_SECRET_KEY
        self.algorithm = JWT_ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = REFRESH_TOKEN_EXPIRE_DAYS
        
        # Token blacklist (in production, use Redis)
        self._blacklisted_tokens: set = set()
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token"""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "type": "access"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token"""
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "type": "refresh"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_token_response(self, user: User) -> TokenResponse:
        """Create complete token response"""
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60
        )
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode JWT token"""
        try:
            # Check if token is blacklisted
            if token in self._blacklisted_tokens:
                return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Validate required fields
            if not all(key in payload for key in ["sub", "email", "role", "exp", "type"]):
                return None
            
            return TokenPayload(**payload)
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Create new access token from refresh token"""
        payload = self.verify_token(refresh_token)
        
        if not payload or payload.type != "refresh":
            return None
        
        # Create new access token with same user info
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        new_payload = {
            "sub": payload.sub,
            "email": payload.email,
            "role": payload.role,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "type": "access"
        }
        
        return jwt.encode(new_payload, self.secret_key, algorithm=self.algorithm)
    
    def revoke_token(self, token: str) -> bool:
        """Add token to blacklist"""
        try:
            payload = self.verify_token(token)
            if payload:
                self._blacklisted_tokens.add(token)
                return True
            return False
        except Exception:
            return False
    
    async def authenticate_user(self, user_repository: UserRepository, 
                               email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await user_repository.get_by_email(email)
        
        if not user or not user.is_active:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        # Update last login
        await user_repository.update_last_login(user.id)
        
        return user

class RolePermissionService:
    """Role-based permission management"""
    
    # Define role permissions
    ROLE_PERMISSIONS = {
        UserRole.ADMIN: [
            "users:*", "cloud_providers:*", "budgets:*", "costs:*", 
            "reports:*", "optimization:*", "compliance:*", "system:*"
        ],
        UserRole.FINANCE_MANAGER: [
            "budgets:*", "costs:read", "costs:write", "reports:*", 
            "optimization:read", "compliance:read", "users:read"
        ],
        UserRole.ANALYST: [
            "costs:read", "reports:read", "reports:write", 
            "optimization:read", "compliance:read", "budgets:read"
        ],
        UserRole.VIEWER: [
            "costs:read", "reports:read", "budgets:read", 
            "optimization:read", "compliance:read"
        ]
    }
    
    def check_permission(self, user_role: UserRole, resource: str, action: str) -> bool:
        """Check if user role has permission for resource:action"""
        permissions = self.ROLE_PERMISSIONS.get(user_role, [])
        
        # Check for wildcard permissions
        if f"{resource}:*" in permissions or "*" in permissions:
            return True
        
        # Check for specific permission
        if f"{resource}:{action}" in permissions:
            return True
        
        return False
    
    def get_user_permissions(self, user_role: UserRole) -> List[str]:
        """Get all permissions for a user role"""
        return self.ROLE_PERMISSIONS.get(user_role, [])
    
    def require_permission(self, resource: str, action: str):
        """Decorator to require specific permission"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # This would be implemented as a FastAPI dependency
                # For now, it's a placeholder
                return func(*args, **kwargs)
            return wrapper
        return decorator

# Global instances
auth_service = AuthenticationService()
permission_service = RolePermissionService()

# FastAPI Dependencies
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
) -> User:
    """FastAPI dependency to get current authenticated user"""
    from app.services.repositories import UserRepository
    
    # Demo mode bypass - if no credentials provided or demo mode enabled
    if os.getenv("DEMO_MODE", "false").lower() == "true" or credentials is None:
        # Return a demo user with correct fields and proper UUID
        from uuid import UUID
        demo_user = User(
            # id=UUID("00000000-0000-0000-0000-000000000000"),
            # email="demo@example.com",
            # password_hash="demo_hash",
            # first_name="Demo",
            # last_name="User",
            # role=UserRole.ADMIN,
            # is_active=True
        )
        return demo_user
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = auth_service.verify_token(token)
        
        if payload is None:
            raise credentials_exception
        
        user_id = UUID(payload.sub)
        user_repository = UserRepository(db)
        user = await user_repository.get_by_id(user_id)
        
        if user is None or not user.is_active:
            raise credentials_exception
        
        return user
    except Exception:
        raise credentials_exception

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency to get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def require_role(required_role: UserRole):
    """FastAPI dependency to require specific role"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role != required_role and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

def require_permission(resource: str, action: str):
    """FastAPI dependency to require specific permission"""
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not permission_service.check_permission(current_user.role, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}"
            )
        return current_user
    return permission_checker

# Permission decorators for common operations
require_admin = require_role(UserRole.ADMIN)
require_finance_manager = require_role(UserRole.FINANCE_MANAGER)

# Resource-specific permissions
require_budget_read = require_permission("budgets", "read")
require_budget_write = require_permission("budgets", "write")
require_cost_read = require_permission("costs", "read")
require_cost_write = require_permission("costs", "write")
require_report_read = require_permission("reports", "read")
require_report_write = require_permission("reports", "write")
require_optimization_read = require_permission("optimization", "read")
require_compliance_read = require_permission("compliance", "read")

class AuthenticationException(Exception):
    """Custom authentication exception"""
    pass

class AuthorizationException(Exception):
    """Custom authorization exception"""
    pass
