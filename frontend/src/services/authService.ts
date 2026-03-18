import { api } from './api';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authService = {
  async login(email: string, password: string): Promise<AuthResponse> {
    const formData = new URLSearchParams();
    formData.append('username', email); // OAuth2 expects username
    formData.append('password', password);
    
    // Check if backend uses JSON or Form Data.
    // Based on `UserLoginRequest` pydantic model in `auth_endpoints.py`, it expects JSON body { email, password }
    // BUT OAuth2PasswordRequestForm expects form data.
    // Let's rely on the `UserLoginRequest` model I saw earlier:
    // class UserLoginRequest(BaseModel): email: EmailStr, password: str
    
    const response = await api.post('/auth/login', { email, password });
    return response.data;
  },

  async register(data: any): Promise<User> {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get('/auth/me');
    return response.data;
  }
};
