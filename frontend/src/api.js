const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

let token = localStorage.getItem('token');

export function setToken(newToken) {
  token = newToken;
  localStorage.setItem('token', newToken);
}

export function clearToken() {
  token = null;
  localStorage.removeItem('token');
}

export function getToken() {
  return token;
}

async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = { ...options.headers };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    window.location.hash = '/login';
    throw new Error('Sesión expirada');
  }

  if (res.status === 204) return null;

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Error en la solicitud');
  }
  return data;
}

async function publicFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = { ...options.headers };

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 204) return null;

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Error en la solicitud');
  }
  return data;
}

export const api = {
  login: (username, password) =>
    apiFetch('/auth/token', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => apiFetch('/auth/me'),

  changePassword: (oldPassword, newPassword) =>
    apiFetch('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),

  getEmailAccounts: () => apiFetch('/email-accounts'),
  createEmailAccount: (data) =>
    apiFetch('/email-accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateEmailAccount: (id, data) =>
    apiFetch(`/email-accounts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteEmailAccount: (id) =>
    apiFetch(`/email-accounts/${id}`, { method: 'DELETE' }),
  testEmailConnection: (id) =>
    apiFetch(`/email-accounts/${id}/test`, { method: 'POST' }),
  pollEmailAccount: (id) =>
    apiFetch(`/email-accounts/${id}/poll`, { method: 'POST' }),

  getPlatforms: () => apiFetch('/platforms'),
  createPlatform: (data) =>
    apiFetch('/platforms', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updatePlatform: (id, data) =>
    apiFetch(`/platforms/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deletePlatform: (id) =>
    apiFetch(`/platforms/${id}`, { method: 'DELETE' }),

  getCodes: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, v);
    });
    const q = qs.toString();
    return apiFetch(`/codes${q ? '?' + q : ''}`);
  },

  getRecentCodes: (minutes = 5) =>
    apiFetch(`/codes/recent?minutes=${minutes}`),

  getCodeStats: () => apiFetch('/codes/stats'),

  markDelivered: (id, deliveredTo) =>
    apiFetch(`/codes/${id}/deliver`, {
      method: 'PUT',
      body: JSON.stringify({ delivered_to: deliveredTo }),
    }),

  markRead: (id) =>
    apiFetch(`/codes/${id}/read`, { method: 'PUT' }),

  getWsUrl: () => {
    const base = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://');
    const t = token || '';
    return `${base}/codes/ws?token=${encodeURIComponent(t)}`;
  },

  ping: () => publicFetch('/public/ping'),

  public: {
    getEmailAccounts: () => publicFetch('/public/email-accounts'),
    getPlatforms: () => publicFetch('/public/platforms'),
    requestCode: (email, platformName) => {
      const params = new URLSearchParams({ email, platform_name: platformName });
      return publicFetch(`/public/request-code?${params}`, {
        method: 'POST',
      });
    },
  },
};
