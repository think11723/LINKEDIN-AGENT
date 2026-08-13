export class ApiError extends Error {
  constructor({ status, message, code, payload }) {
    super(message || 'Request failed');
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

const DEFAULT_BASE_URL = 'http://localhost:8000';

function resolveBaseUrl() {
  const raw = import.meta.env.VITE_API_BASE_URL;
  return (raw && raw.replace(/\/$/, '')) || DEFAULT_BASE_URL;
}

// H2 (Phase 8C) - status-aware safe messages. The backend's detail
// string is preferred for 4xx because it is the app's own text; for
// 401/403/404/409/429/5xx we override with a clear, copy-stable message
// so the SPA never has to depend on the backend's exception text.
const STATUS_MESSAGES = {
  401: 'Your session has expired. Please sign in again.',
  403: 'You do not have permission to perform this action.',
  404: 'This resource could not be found.',
  409: 'This action conflicts with the current state.',
  422: 'The request was rejected as invalid.',
  429: 'Too many requests. Please try again shortly.',
  500: 'Something went wrong on our server. Please try again.',
  502: 'The upstream service is unavailable. Please try again.',
  503: 'The service is temporarily unavailable. Please try again.',
  504: 'The upstream service timed out. Please try again.',
};

function describeError(payload, status) {
  if (status && STATUS_MESSAGES[status]) {
    return STATUS_MESSAGES[status];
  }
  if (!payload) return null;
  if (typeof payload === 'string') return payload;
  if (Array.isArray(payload)) {
    return payload
      .map((entry) => entry?.msg || entry?.message || JSON.stringify(entry))
      .filter(Boolean)
      .join('; ');
  }
  if (typeof payload === 'object') {
    return payload.detail || payload.message || payload.error || JSON.stringify(payload);
  }
  return null;
}

export async function request({
  method = 'GET',
  path,
  body,
  token,
  signal,
  headers = {},
}) {
  const url = `${resolveBaseUrl()}${path}`;
  const finalHeaders = { Accept: 'application/json', ...headers };

  let payload;
  if (body !== undefined && body !== null) {
    finalHeaders['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  if (token) {
    finalHeaders.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: payload,
      signal,
    });
  } catch (err) {
    if (err?.name === 'AbortError') throw err;
    throw new ApiError({
      status: 0,
      message: 'Unable to reach the backend. Check your network or API URL.',
      code: 'network_error',
    });
  }

  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      message:
        describeError(data, response.status) ||
        response.statusText ||
        'Request failed',
      code: response.status === 401 ? 'unauthorized' : `http_${response.status}`,
      payload: data,
    });
  }

  return data;
}