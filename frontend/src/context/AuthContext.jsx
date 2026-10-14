import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getMe } from '../api/auth.js';
import {
  AUTH_REFRESH_TIMEOUT_MS,
  clearApiAuthorization,
  isDefinitiveAuthFailure,
  setApiAuthorization,
} from '../api/axios.js';
import {
  clearStoredSession,
  getAccessToken,
  storeSession,
  subscribeSessionExpired,
  withTimeout,
} from '../api/session.js';

const AuthContext = createContext(null);

const AUTH_RESTORE_TIMEOUT_MS = 30000; // 30 seconds for session restore

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const restoreGeneration = useRef(0);

  const cancelRestore = useCallback(() => {
    restoreGeneration.current += 1;
  }, []);

  const loginUser = useCallback((userData, accessToken, refreshToken) => {
    // Validate and persist before changing React state. In particular,
    // undefined access_token values must never become the literal string
    // "undefined" in localStorage.
    if (!storeSession({ accessToken, refreshToken })) {
      throw new Error('Unable to persist authentication session');
    }
    cancelRestore();
    setApiAuthorization(accessToken);
    setUser(userData);
    setLoading(false);
  }, [cancelRestore]);

  const logoutUser = useCallback(() => {
    cancelRestore();
    clearStoredSession();
    clearApiAuthorization();
    setUser(null);
    setLoading(false);
  }, [cancelRestore]);

  // On mount: restore the session and ignore any result superseded by a
  // login, logout, StrictMode cleanup/re-run, or provider unmount.
  useEffect(() => {
    let active = true;
    const operation = ++restoreGeneration.current;
    const isCurrent = () => active && restoreGeneration.current === operation;

    const unsubscribe = subscribeSessionExpired((detail = {}) => {
      if (!active) return;

      // A request from an older session must not log out a newly authenticated
      // user. Axios includes the token that failed when it emits the event.
      const currentToken = getAccessToken();
      if (detail.accessToken && currentToken && detail.accessToken !== currentToken) return;

      restoreGeneration.current += 1;
      clearStoredSession();
      clearApiAuthorization();
      setUser(null);
      setLoading(false);
    });

    const token = getAccessToken();
    if (!token) {
      clearApiAuthorization();
      if (isCurrent()) setLoading(false);
    } else {
      setLoading(true);
      withTimeout(
        getMe({ timeout: AUTH_RESTORE_TIMEOUT_MS }),
        AUTH_RESTORE_TIMEOUT_MS,
        'Session restore timed out',
        'AUTH_RESTORE_TIMEOUT',
      )
        .then(({ data }) => {
          if (isCurrent()) setUser(data.user || data);
        })
        .catch((error) => {
          if (!isCurrent()) return;

          // Axios emits the event for definitive 401/403 failures. Keep the
          // same behavior here for adapters or mocked clients that reject
          // before the interceptor can do so, while retaining tokens for
          // network/server outages.
          if (isDefinitiveAuthFailure(error)) {
            clearStoredSession();
            clearApiAuthorization();
          }
          setUser(null);
        })
        .finally(() => {
          if (isCurrent()) setLoading(false);
        });
    }

    return () => {
      active = false;
      restoreGeneration.current += 1;
      unsubscribe();
    };
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, loginUser, logoutUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
