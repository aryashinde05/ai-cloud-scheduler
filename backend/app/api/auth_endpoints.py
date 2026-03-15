"""
Authentication endpoints for FinOps Platform
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, validator
from supabase import Client

from app.core.auth import (
    auth_service, AuthenticationService, TokenResponse, 
    get_current_user, get_current_active_user, security
)
from app.models.models import User, UserRole
from app.services.repositories import UserRepository, AuditLogRepository
from app.database.database import get_supabase

# Create router
auth_router = APIRouter(prefix="/auth", tags=["authentication"])

# Request/Response Models
class UserRegistrationRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.VIEWER
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        # Check for at least one uppercase, lowercase, digit, and special character
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one digit, and one special character'
            )
        
        return v

class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """User response model"""
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    last_login: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True

class PasswordChangeRequest(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one digit, and one special character'
            )
        
        return v

class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str

# Helper functions
def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def get_user_agent(request: Request) -> str:
    """Get user agent from request"""
    return request.headers.get("User-Agent", "unknown")

# Authentication Endpoints

@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistrationRequest,
    request: Request,
    db: Client = Depends(get_supabase)
):
    """Register a new user"""
    user_repo = UserRepository(db)
    audit_repo = AuditLogRepository(db)
    
    # Check if user already exists
    existing_user = await user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    try:
        # Hash password
        password_hash = auth_service.hash_password(user_data.password)
        
        # Create user
        user = await user_repo.create(
            email=user_data.email,
            password_hash=password_hash,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role
        )
        
        # Log registration
        await audit_repo.log_action(
            user_id=user.id,
            action="user_registered",
            resource_type="user",
            resource_id=str(user.id),
            new_values={
                "email": user.email,
                "role": user.role.value
            },
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        return UserResponse.from_orm(user)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {str(e)}"
        )

@auth_router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLoginRequest,
    request: Request,
    db: Client = Depends(get_supabase)
):
    """Authenticate user and return tokens"""
    user_repo = UserRepository(db)
    audit_repo = AuditLogRepository(db)
    
    # Authenticate user
    user = await auth_service.authenticate_user(
        user_repo, login_data.email, login_data.password
    )
    
    if not user:
        # Log failed login attempt
        try:
            existing_user = await user_repo.get_by_email(login_data.email)
            if existing_user:
                await audit_repo.log_action(
                    user_id=existing_user.id,
                    action="login_failed",
                    resource_type="user",
                    resource_id=str(existing_user.id),
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
        except:
            pass  # Don't fail if audit logging fails
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Create tokens
        token_response = auth_service.create_token_response(user)
        
        # Log successful login
        await audit_repo.log_action(
            user_id=user.id,
            action="login_success",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        return token_response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tokens: {str(e)}"
        )

@auth_router.post("/refresh", response_model=dict)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: Client = Depends(get_supabase)
):
    """Refresh access token using refresh token"""
    audit_repo = AuditLogRepository(db)
    
    try:
        # Verify refresh token and create new access token
        new_access_token = auth_service.refresh_access_token(refresh_data.refresh_token)
        
        if not new_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user info from token for logging
        payload = auth_service.verify_token(refresh_data.refresh_token)
        if payload:
            await audit_repo.log_action(
                user_id=UUID(payload.sub),
                action="token_refreshed",
                resource_type="user",
                resource_id=payload.sub,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": auth_service.access_token_expire_minutes * 60
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )

@auth_router.post("/logout")
async def logout_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """Logout user and revoke token"""
    audit_repo = AuditLogRepository(db)
    
    try:
        # Revoke the token
        token = credentials.credentials
        auth_service.revoke_token(token)
        
        # Log logout
        await audit_repo.log_action(
            user_id=current_user.id,
            action="logout",
            resource_type="user",
            resource_id=str(current_user.id),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        return {"message": "Successfully logged out"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout: {str(e)}"
        )

@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return UserResponse.from_orm(current_user)

@auth_router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: dict,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """Update current user information"""
    user_repo = UserRepository(db)
    audit_repo = AuditLogRepository(db)
    
    try:
        # Only allow updating certain fields
        allowed_fields = ['first_name', 'last_name']
        update_data = {k: v for k, v in user_update.items() if k in allowed_fields}
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Store old values for audit
        old_values = {k: getattr(current_user, k) for k in update_data.keys()}
        
        # Update user
        updated_user = await user_repo.update(current_user.id, **update_data)
        
        # Log update
        await audit_repo.log_action(
            user_id=current_user.id,
            action="user_updated",
            resource_type="user",
            resource_id=str(current_user.id),
            old_values=old_values,
            new_values=update_data,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        return UserResponse.from_orm(updated_user)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@auth_router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """Change user password"""
    user_repo = UserRepository(db)
    audit_repo = AuditLogRepository(db)
    
    # Verify current password
    if not auth_service.verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Check if new password is different
    if auth_service.verify_password(password_data.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    try:
        # Hash new password
        new_password_hash = auth_service.hash_password(password_data.new_password)
        
        # Update password
        await user_repo.update(
            current_user.id,
            password_hash=new_password_hash,
            password_changed_at=datetime.utcnow()
        )
        
        # Log password change
        await audit_repo.log_action(
            user_id=current_user.id,
            action="password_changed",
            resource_type="user",
            resource_id=str(current_user.id),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        return {"message": "Password changed successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )

@auth_router.get("/permissions")
async def get_user_permissions(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's permissions"""
    from app.core.auth import permission_service
    
    permissions = permission_service.get_user_permissions(current_user.role)
    
    return {
        "user_id": current_user.id,
        "role": current_user.role.value,
        "permissions": permissions
    }

# Admin-only endpoints
@auth_router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """List all users (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    user_repo = UserRepository(db)
    users = await user_repo.get_all(limit=limit, offset=skip)
    
    return [UserResponse.from_orm(user) for user in users]

@auth_router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    new_role: UserRole,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """Update user role (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    user_repo = UserRepository(db)
    audit_repo = AuditLogRepository(db)
    
    # Get target user
    target_user = await user_repo.get_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        old_role = target_user.role
        
        # Update role
        await user_repo.update(user_id, role=new_role)
        
        # Log role change
        await audit_repo.log_action(
            user_id=current_user.id,
            action="user_role_changed",
            resource_type="user",
            resource_id=str(user_id),
            old_values={"role": old_role.value},
            new_values={"role": new_role.value},
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        
        return {"message": f"User role updated to {new_role.value}"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user role: {str(e)}"
        )
