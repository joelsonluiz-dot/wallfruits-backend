import { API_BASE_URL } from './config';

export type ApiUser = {
  id: number;
  name: string;
  email: string;
  role: string;
  platform_role?: string | null;
  account_role?: string | null;
  account_scope_id?: string | null;
  profile_image?: string | null;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: ApiUser;
};

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Falha ao autenticar');
  }

  return response.json() as Promise<LoginResponse>;
}

export async function fetchMe(token: string): Promise<ApiUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Nao foi possivel carregar o usuario autenticado');
  }

  return response.json() as Promise<ApiUser>;
}
