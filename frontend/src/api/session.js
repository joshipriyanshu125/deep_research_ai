export const ACCESS_TOKEN_KEY = 'accessToken';
export const REFRESH_TOKEN_KEY = 'refreshToken';
export const SESSION_EXPIRED_EVENT = 'auth:session-expired';

const sessionExpiredListeners = new Set();
let sessionExpiredEmitted = false;

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return typeof globalThis !== 'undefined' && globalThis.localStorage
      ? globalThis.localStorage
      : null;
  } catch {
    return null;
  }
}

function readItem(storage, key) {
  if (!storage || typeof storage.getItem !== 'function') return null;

  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function writeItem(storage, key, value) {
  if (!storage || typeof storage.setItem !== 'function') return false;

  try {
    storage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function removeItem(storage, key) {
  if (!storage || typeof storage.removeItem !== 'function') return false;

  try {
    storage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

export function isUsableToken(value) {
  return typeof value === 'string'
    && value.trim().length > 0
    && value !== 'undefined'
    && value !== 'null';
}

export function getStoredValue(key, storage) {
  return readItem(resolveStorage(storage), key);
}

export function getAccessToken(storage) {
  const token = getStoredValue(ACCESS_TOKEN_KEY, storage);
  return isUsableToken(token) ? token : null;
}

export function getRefreshToken(storage) {
  const token = getStoredValue(REFRESH_TOKEN_KEY, storage);
  return isUsableToken(token) ? token : null;
}

/**
 * Persist a newly authenticated session. An access token is mandatory. A
 * missing refresh token deliberately removes any token left by a prior
 * provider, which matters when switching to the Python access-token-only API.
 */
export function storeSession({ accessToken, refreshToken } = {}, storage) {
  if (!isUsableToken(accessToken)) {
    throw new Error('Authentication response did not include a valid access token');
  }

  const target = resolveStorage(storage);
  if (!writeItem(target, ACCESS_TOKEN_KEY, accessToken)) return false;

  const refreshStored = isUsableToken(refreshToken)
    ? writeItem(target, REFRESH_TOKEN_KEY, refreshToken)
    : removeItem(target, REFRESH_TOKEN_KEY);

  if (!refreshStored) {
    // Do not leave a partially written session behind when storage is not
    // available. This also prevents a stale refresh token from surviving a
    // token-only login response.
    removeItem(target, ACCESS_TOKEN_KEY);
    return false;
  }

  resetSessionExpiredEvent();
  return true;
}

export function setAccessToken(accessToken, storage) {
  if (!isUsableToken(accessToken)) {
    throw new Error('Cannot store an invalid access token');
  }

  const stored = writeItem(resolveStorage(storage), ACCESS_TOKEN_KEY, accessToken);
  if (stored) resetSessionExpiredEvent();
  return stored;
}

export function setRefreshToken(refreshToken, storage) {
  if (!isUsableToken(refreshToken)) return false;
  return writeItem(resolveStorage(storage), REFRESH_TOKEN_KEY, refreshToken);
}

export function clearStoredSession(storage) {
  const target = resolveStorage(storage);
  removeItem(target, ACCESS_TOKEN_KEY);
  removeItem(target, REFRESH_TOKEN_KEY);
}

export function resetSessionExpiredEvent() {
  sessionExpiredEmitted = false;
}

function getEventTarget() {
  try {
    return typeof globalThis !== 'undefined' && globalThis.window
      ? globalThis.window
      : null;
  } catch {
    return null;
  }
}

export function subscribeSessionExpired(listener) {
  if (typeof listener !== 'function') return () => {};

  // Keep a fallback registration as well as the browser listener. This lets a
  // partial DOM shim (addEventListener without dispatchEvent) behave like the
  // browser implementation without making Node tests depend on a DOM.
  sessionExpiredListeners.add(listener);
  const target = getEventTarget();
  if (target && typeof target.addEventListener === 'function') {
    const handler = (event) => listener(event?.detail);
    target.addEventListener(SESSION_EXPIRED_EVENT, handler);
    return () => {
      sessionExpiredListeners.delete(listener);
      if (typeof target.removeEventListener === 'function') {
        target.removeEventListener(SESSION_EXPIRED_EVENT, handler);
      }
    };
  }

  return () => sessionExpiredListeners.delete(listener);
}

/**
 * Notify the AuthProvider without taking over browser navigation. The
 * in-memory fallback keeps this usable in Node tests and non-DOM renders.
 */
export function emitSessionExpired(detail = {}) {
  if (sessionExpiredEmitted) return false;
  sessionExpiredEmitted = true;

  const target = getEventTarget();
  if (target && typeof target.dispatchEvent === 'function') {
    try {
      const EventConstructor = target.CustomEvent
        || (typeof CustomEvent !== 'undefined' ? CustomEvent : null);
      const event = EventConstructor
        ? new EventConstructor(SESSION_EXPIRED_EVENT, { detail })
        : { type: SESSION_EXPIRED_EVENT, detail };
      target.dispatchEvent(event);
      return true;
    } catch {
      // Fall through to the in-memory listeners when a partial DOM shim is in
      // use (as is common in tests).
    }
  }

  [...sessionExpiredListeners].forEach((listener) => listener(detail));
  return true;
}

/**
 * Bound auth bootstrap and refresh operations even when an adapter ignores
 * Axios' own timeout option.
 */
export function withTimeout(value, milliseconds, message = 'Authentication request timed out', code = 'AUTH_TIMEOUT') {
  const timeout = Math.max(0, Number(milliseconds) || 0);

  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      const error = new Error(message);
      error.code = code;
      reject(error);
    }, timeout);

    Promise.resolve(value).then(
      (result) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(result);
      },
      (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}
