import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
});

// Translate backend error shape into thrown error with consistent message
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const data = error.response?.data;
    const message = data?.error || error.message || 'Request failed';
    const code = data?.code || (status ? `HTTP_${status}` : 'NETWORK_ERROR');
    const requestId = data?.request_id;
    const wrapped = new Error(`${code}: ${message}${requestId ? ` (req ${requestId})` : ''}`);
    wrapped.status = status;
    wrapped.code = code;
    wrapped.requestId = requestId;
    return Promise.reject(wrapped);
  }
);

/** Helper for paginated list endpoints. */
export async function listPaginated(endpoint, params = {}) {
  const response = await api.get(endpoint, { params });
  return response.data;
}
