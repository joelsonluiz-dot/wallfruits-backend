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

type OffersResponse = {
  total: number;
};

type StoreOrdersResponse = {
  total: number;
};

export type DashboardSnapshot = {
  offersTotal: number;
  ordersTotal: number;
  aiSignals: number;
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

export async function fetchDashboardSnapshot(token: string): Promise<DashboardSnapshot> {
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/json',
  };

  const [offersRes, ordersRes, aiRes] = await Promise.all([
    fetch(`${API_BASE_URL}/api/offers?skip=0&limit=5`, { headers }),
    fetch(`${API_BASE_URL}/api/store/orders/my`, { headers }),
    fetch(`${API_BASE_URL}/api/ai/agenda/market-intelligence`, { headers }),
  ]);

  if (!offersRes.ok || !ordersRes.ok || !aiRes.ok) {
    throw new Error('Falha ao carregar dashboard integrado');
  }

  const offers = (await offersRes.json()) as OffersResponse;
  const orders = (await ordersRes.json()) as StoreOrdersResponse;
  const ai = (await aiRes.json()) as Record<string, unknown>;

  const alerts = Array.isArray(ai.alerts) ? ai.alerts.length : 0;
  const opportunities = Array.isArray(ai.opportunities) ? ai.opportunities.length : 0;
  const recommendations = Array.isArray(ai.recommendations) ? ai.recommendations.length : 0;

  return {
    offersTotal: Number(offers.total ?? 0),
    ordersTotal: Number(orders.total ?? 0),
    aiSignals: alerts + opportunities + recommendations,
  };
}
