import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

// Attach access token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401 → try refresh, then retry original request (for authenticated protected requests only)
let isRefreshing = false;
let failQueue = [];

const processQueue = (error, token = null) => {
  failQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failQueue = [];
};

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // The API and MongoDB may still be starting when Vite becomes ready.
    // Retry only transient connection/startup failures; authentication
    // failures (401) must still reach the login screen immediately.
    const transientStatus = [502, 503, 504].includes(error.response?.status);
    const transientNetworkError = !error.response && [
      'ERR_NETWORK',
      'ECONNREFUSED',
      'ECONNRESET',
      'ETIMEDOUT',
    ].includes(error.code);
    const retryCount = originalRequest?._connectionRetryCount || 0;

    if (originalRequest && (transientStatus || transientNetworkError) && retryCount < 6) {
      originalRequest._connectionRetryCount = retryCount + 1;
      await wait(250 * (2 ** retryCount));
      return api(originalRequest);
    }

    // Do NOT intercept auth endpoints like /login or /register or /refresh on 401
    const url = originalRequest?.url || '';
    const isAuthRoute =
      url.includes('/auth/login') ||
      url.includes('/auth/register') ||
      url.includes('/auth/refresh') ||
      url.includes('/auth/forgot-password') ||
      url.includes('/auth/reset-password');

    const refreshToken = localStorage.getItem('refreshToken');

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRoute && refreshToken) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await axios.post('/api/auth/refresh', { refreshToken });
        const newToken = data.accessToken || data.token || data.access_token;
        const newRefresh = data.refreshToken || data.refresh_token;
        localStorage.setItem('accessToken', newToken);
        if (newRefresh) localStorage.setItem('refreshToken', newRefresh);
        api.defaults.headers.common.Authorization = `Bearer ${newToken}`;
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
