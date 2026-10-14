import axios from 'axios';
import {
  clearStoredSession,
  emitSessionExpired,
  getAccessToken,
  getRefreshToken,
  isUsableToken,
  setAccessToken,
  setRefreshToken,
  withTimeout,
} from './session.js';

export const AUTH_REFRESH_TIMEOUT_MS = 30000;
export const AUTH_RETRY_LIMIT = 1;

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

function setHeader(headers, name, value) {
  if (!headers) return;
  if (typeof headers.set === 'function') headers.set(name, value);
  else headers[name] = value;
}

function deleteHeader(headers, name) {
  if (!headers) return;
  if (typeof headers.delete === 'function') headers.delete(name);
  else delete headers[name];
}

export function setApiAuthorization(token) {
  if (!isUsableToken(token)) return;
  const commonHeaders = api.defaults.headers?.common;
  setHeader(commonHeaders, 'Authorization', `Bearer ${token}`);
}

export function clearApiAuthorization() {
  const commonHeaders = api.defaults.headers?.common;
  deleteHeader(commonHeaders, 'Authorization');
  deleteHeader(commonHeaders, 'authorization');
}

// Attach access token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    // Keep the credential that was current when this request was created.
    // An old restore request must not clear a newer login if its response
    // arrives after the user changes sessions.
    config._authAccessToken = token;
    config._authRefreshToken = getRefreshToken();
    config.headers = config.headers || {};
    setHeader(config.headers, 'Authorization', `Bearer ${token}`);
  } else {
    // Axios merges instance defaults into each config. Remove an old default
    // rather than allowing a logged-out request to keep sending it.
    deleteHeader(config.headers, 'Authorization');
    deleteHeader(config.headers, 'authorization');
  }
  return config;
});

// On 401 → try refresh, then retry the original request (for authenticated
// protected requests only). The retry marker is applied before queueing so a
// request released from the queue cannot start an unbounded refresh loop.
let isRefreshing = false;
let failQueue = [];

const processQueue = (error, token = null) => {
  const queue = failQueue;
  failQueue = [];
  queue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
};

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const transientConnectionStatuses = [502, 503, 504];
const transientNetworkCodes = [
  'ERR_NETWORK',
  'ECONNREFUSED',
  'ECONNRESET',
  'ETIMEDOUT',
  'ECONNABORTED',
  'EAI_AGAIN',
];

function isTransientConnectionFailure(error) {
  return transientConnectionStatuses.includes(error.response?.status)
    || (!error.response && transientNetworkCodes.includes(error.code));
}

function isDefinitiveAuthFailure(error) {
  return [401, 403].includes(error.response?.status);
}

function isDefinitiveRefreshFailure(error) {
  if (error?.code === 'AUTH_REFRESH_INVALID_RESPONSE') return true;

  const status = error?.response?.status;
  // 408/429 are temporary request throttling/timeouts. Other client errors
  // mean the refresh contract rejected the credential (including unsupported
  // refresh routes returning 404).
  return typeof status === 'number'
    && status >= 400
    && status < 500
    && ![408, 429].includes(status);
}

function requestUrl(config) {
  return `${config?.baseURL || ''}${config?.url || ''}`;
}

function isAuthRoute(config) {
  const url = requestUrl(config);
  return url.includes('/auth/login')
    || url.includes('/auth/register')
    || url.includes('/auth/logout')
    || url.includes('/auth/refresh')
    || url.includes('/auth/forgot-password')
    || url.includes('/auth/reset-password');
}

function getBearerToken(config) {
  const headers = config?.headers;
  if (!headers) return null;

  const value = typeof headers.get === 'function'
    ? headers.get('Authorization') || headers.get('authorization')
    : headers.Authorization || headers.authorization;

  if (typeof value !== 'string' || !value.startsWith('Bearer ')) return null;
  return value.slice('Bearer '.length);
}

function failedAccessToken(config) {
  return config?._authAccessToken || getBearerToken(config) || getAccessToken();
}

function expireSession(error, accessToken) {
  const currentAccessToken = getAccessToken();
  if (
    isUsableToken(accessToken)
    && isUsableToken(currentAccessToken)
    && accessToken !== currentAccessToken
  ) {
    return false;
  }

  clearStoredSession();
  clearApiAuthorization();
  emitSessionExpired({
    reason: error?.code || `HTTP_${error?.response?.status || 'AUTH'}`,
    accessToken: isUsableToken(accessToken) ? accessToken : undefined,
  });
}

function retryWithToken(originalRequest, token) {
  originalRequest.headers = originalRequest.headers || {};
  setHeader(originalRequest.headers, 'Authorization', `Bearer ${token}`);
  return api(originalRequest);
}

function invalidRefreshResponseError() {
  const error = new Error('Refresh response did not include a valid access token');
  error.code = 'AUTH_REFRESH_INVALID_RESPONSE';
  return error;
}

function firstUsableToken(...values) {
  return values.find(isUsableToken) || null;
}

function requestRefreshToken(refreshToken) {
  const request = Promise.resolve().then(() => axios.post(
    '/api/auth/refresh',
    { refreshToken },
    {
      timeout: AUTH_REFRESH_TIMEOUT_MS,
      withCredentials: true,
    },
  ));

  return withTimeout(
    request,
    AUTH_REFRESH_TIMEOUT_MS,
    'Authentication refresh timed out',
    'AUTH_REFRESH_TIMEOUT',
  );
}

function refreshAccessToken(refreshToken, accessToken) {
  isRefreshing = true;

  const refreshPromise = requestRefreshToken(refreshToken)
    .then(({ data = {} }) => {
      const currentAccessToken = getAccessToken();
      if (
        isUsableToken(accessToken)
        && accessToken !== currentAccessToken
      ) {
        const error = new Error('Authentication refresh belongs to an older session');
        error.code = 'AUTH_REFRESH_STALE';
        throw error;
      }

      const newToken = firstUsableToken(data.accessToken, data.access_token, data.token);
      if (!isUsableToken(newToken)) throw invalidRefreshResponseError();

      if (!setAccessToken(newToken)) {
        const error = new Error('Unable to persist refreshed access token');
        error.code = 'AUTH_REFRESH_STORAGE_FAILURE';
        throw error;
      }

      const newRefreshToken = firstUsableToken(data.refreshToken, data.refresh_token);
      if (isUsableToken(newRefreshToken)) setRefreshToken(newRefreshToken);

      setApiAuthorization(newToken);
      // Release the single-flight lock before resolving queued promises. A
      // caller may synchronously start another request from a rejection/then
      // handler, and it must never be stranded in a queue that was already
      // drained.
      isRefreshing = false;
      processQueue(null, newToken);
      return newToken;
    })
    .catch((refreshError) => {
      if (isDefinitiveRefreshFailure(refreshError)) {
        expireSession(refreshError, accessToken);
      }
      isRefreshing = false;
      processQueue(refreshError, null);
      throw refreshError;
    })
    .finally(() => {
      isRefreshing = false;
    });

  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // The API and MongoDB may still be starting when Vite becomes ready.
    // Retry only transient connection/startup failures; authentication
    // failures (401/403) are handled below.
    const retryCount = originalRequest?._connectionRetryCount || 0;

    if (originalRequest && isTransientConnectionFailure(error) && retryCount < 6) {
      originalRequest._connectionRetryCount = retryCount + 1;
      await wait(250 * (2 ** retryCount));
      return api(originalRequest);
    }

    // Do NOT intercept public auth endpoints like /login or /register. A
    // protected 403 is definitive and never benefits from a refresh attempt.
    const protectedRequest = originalRequest && !isAuthRoute(originalRequest);
    if (protectedRequest && error.response?.status === 403) {
      expireSession(error, failedAccessToken(originalRequest));
      return Promise.reject(error);
    }

    if (protectedRequest && error.response?.status === 401) {
      const refreshToken = originalRequest._authRefreshToken || getRefreshToken();
      const authRetryCount = Number(originalRequest._authRetryCount)
        || (originalRequest._retry ? 1 : 0);

      if (authRetryCount < AUTH_RETRY_LIMIT && refreshToken) {
        // Mark before waiting so queued requests are each allowed exactly one
        // replay after the shared refresh completes.
        originalRequest._authRetryCount = authRetryCount + 1;
        originalRequest._retry = true;

        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failQueue.push({ resolve, reject });
          }).then((token) => retryWithToken(originalRequest, token));
        }

        return refreshAccessToken(refreshToken, failedAccessToken(originalRequest))
          .then((token) => retryWithToken(originalRequest, token));
      }

      // No refresh credential, or an already retried request, is a real
      // authentication failure. Notify AuthProvider; never hard-navigate.
      expireSession(error, failedAccessToken(originalRequest));
    }

    return Promise.reject(error);
  },
);

export { isDefinitiveAuthFailure, isDefinitiveRefreshFailure };

export default api;
