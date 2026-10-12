import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it } from 'node:test';
import axios, { AxiosError } from 'axios';
import api, {
  clearApiAuthorization,
  setApiAuthorization,
} from '../src/api/axios.js';
import {
  clearStoredSession,
  emitSessionExpired,
  getAccessToken,
  getRefreshToken,
  resetSessionExpiredEvent,
  subscribeSessionExpired,
} from '../src/api/session.js';

class MemoryStorage {
  #values = new Map();

  getItem(key) {
    return this.#values.has(key) ? this.#values.get(key) : null;
  }

  setItem(key, value) {
    this.#values.set(key, String(value));
  }

  removeItem(key) {
    this.#values.delete(key);
  }
}

function response(config, status, data = {}) {
  return {
    data,
    status,
    statusText: String(status),
    headers: {},
    config,
  };
}

function rejected(config, status, data = {}) {
  return new AxiosError(`HTTP ${status}`, 'ERR_BAD_REQUEST', config, null, response(config, status, data));
}

function installAdapters(apiAdapter, refreshAdapter) {
  api.defaults.adapter = apiAdapter;
  axios.defaults.adapter = refreshAdapter;
}

describe('bounded frontend auth recovery', () => {
  let storage;
  let originalStorage;
  let originalWindow;

  beforeEach(() => {
    storage = new MemoryStorage();
    originalStorage = globalThis.localStorage;
    originalWindow = globalThis.window;
    globalThis.localStorage = storage;
    globalThis.window = { location: { href: '/dashboard' } };
    clearStoredSession();
    clearApiAuthorization();
    resetSessionExpiredEvent();
  });

  afterEach(() => {
    clearStoredSession();
    clearApiAuthorization();
    resetSessionExpiredEvent();
    if (originalStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = originalStorage;
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
  });

  it('expires a protected 401 without a refresh token and never hard-navigates', async () => {
    storage.setItem('accessToken', 'expired-access');
    let calls = 0;
    let expiredEvents = 0;
    const unsubscribe = subscribeSessionExpired(() => { expiredEvents += 1; });

    installAdapters(
      async (config) => {
        calls += 1;
        throw rejected(config, 401);
      },
      async () => { throw new Error('refresh must not be called'); },
    );

    await assert.rejects(api.get('/research/protected'));
    assert.equal(calls, 1);
    assert.equal(expiredEvents, 1);
    assert.equal(getAccessToken(), null);
    assert.equal(globalThis.window.location.href, '/dashboard');
    unsubscribe();
  });

  it('refreshes a protected 401 once and retries with the new token', async () => {
    storage.setItem('accessToken', 'expired-access');
    storage.setItem('refreshToken', 'refresh-one');
    let protectedCalls = 0;
    let refreshCalls = 0;

    installAdapters(
      async (config) => {
        protectedCalls += 1;
        if (protectedCalls === 1) throw rejected(config, 401);
        return response(config, 200, { ok: true });
      },
      async (config) => {
        refreshCalls += 1;
        return response(config, 200, {
          access_token: 'fresh-access',
          refreshToken: 'refresh-two',
        });
      },
    );

    const result = await api.get('/research/protected');
    assert.equal(result.data.ok, true);
    assert.equal(protectedCalls, 2);
    assert.equal(refreshCalls, 1);
    assert.equal(getAccessToken(), 'fresh-access');
    assert.equal(getRefreshToken(), 'refresh-two');
  });

  it('shares one refresh across concurrent protected failures and marks queued retries', async () => {
    storage.setItem('accessToken', 'expired-access');
    storage.setItem('refreshToken', 'refresh-one');
    let protectedCalls = 0;
    let refreshCalls = 0;
    let releaseRefresh;
    const refreshReleased = new Promise((resolve) => { releaseRefresh = resolve; });

    installAdapters(
      async (config) => {
        protectedCalls += 1;
        if (protectedCalls <= 2) throw rejected(config, 401);
        return response(config, 200, { ok: true });
      },
      async (config) => {
        refreshCalls += 1;
        await refreshReleased;
        return response(config, 200, { accessToken: 'fresh-access' });
      },
    );

    const first = api.get('/research/one');
    const second = api.get('/research/two');
    await new Promise((resolve) => setTimeout(resolve, 0));
    releaseRefresh();
    const results = await Promise.all([first, second]);

    assert.equal(results.length, 2);
    assert.equal(refreshCalls, 1);
    assert.equal(protectedCalls, 4);
  });

  it('retains the session when refresh is temporarily unavailable', async () => {
    storage.setItem('accessToken', 'expired-access');
    storage.setItem('refreshToken', 'refresh-one');
    let expiredEvents = 0;
    const unsubscribe = subscribeSessionExpired(() => { expiredEvents += 1; });

    installAdapters(
      async (config) => { throw rejected(config, 401); },
      async (config) => { throw rejected(config, 503); },
    );

    await assert.rejects(api.get('/research/protected'));
    assert.equal(expiredEvents, 0);
    assert.equal(getAccessToken(), 'expired-access');
    assert.equal(getRefreshToken(), 'refresh-one');
    assert.equal(globalThis.window.location.href, '/dashboard');
    unsubscribe();
  });

  it('retains the session when refresh has a transient network failure', async () => {
    storage.setItem('accessToken', 'expired-access');
    storage.setItem('refreshToken', 'refresh-one');
    let expiredEvents = 0;
    const unsubscribe = subscribeSessionExpired(() => { expiredEvents += 1; });

    installAdapters(
      async (config) => { throw rejected(config, 401); },
      async () => {
        const error = new Error('offline');
        error.code = 'ERR_NETWORK';
        throw error;
      },
    );

    await assert.rejects(api.get('/research/protected'));
    assert.equal(expiredEvents, 0);
    assert.equal(getAccessToken(), 'expired-access');
    assert.equal(getRefreshToken(), 'refresh-one');
    unsubscribe();
  });

  it('expires when a refresh endpoint is definitively unsupported', async () => {
    storage.setItem('accessToken', 'expired-access');
    storage.setItem('refreshToken', 'refresh-one');
    let expiredEvents = 0;
    const unsubscribe = subscribeSessionExpired(() => { expiredEvents += 1; });

    installAdapters(
      async (config) => { throw rejected(config, 401); },
      async (config) => { throw rejected(config, 404); },
    );

    await assert.rejects(api.get('/research/protected'));
    assert.equal(expiredEvents, 1);
    assert.equal(getAccessToken(), null);
    assert.equal(getRefreshToken(), null);
    assert.equal(globalThis.window.location.href, '/dashboard');
    unsubscribe();
  });

  it('stops after one replay when the refreshed access token is still rejected', async () => {
    storage.setItem('accessToken', 'expired-access');
    storage.setItem('refreshToken', 'refresh-one');
    let protectedCalls = 0;
    let refreshCalls = 0;

    installAdapters(
      async (config) => {
        protectedCalls += 1;
        throw rejected(config, 401);
      },
      async (config) => {
        refreshCalls += 1;
        return response(config, 200, { accessToken: 'fresh-access' });
      },
    );

    await assert.rejects(api.get('/research/protected'));
    assert.equal(protectedCalls, 2);
    assert.equal(refreshCalls, 1);
    assert.equal(getAccessToken(), null);

    assert.equal(globalThis.window.location.href, '/dashboard');
  });

  it('clears a stale default Authorization header explicitly', () => {
    setApiAuthorization('old-token');
    assert.equal(api.defaults.headers.common.Authorization, 'Bearer old-token');
    clearApiAuthorization();
    assert.equal(api.defaults.headers.common.Authorization, undefined);
  });

  it('does not store an undefined access token and removes an old refresh token', async () => {
    storage.setItem('accessToken', 'old-access');
    storage.setItem('refreshToken', 'old-refresh');

    const { storeSession } = await import('../src/api/session.js');
    assert.throws(() => storeSession({ accessToken: undefined }), /valid access token/);
    assert.equal(storeSession({ accessToken: 'new-access' }), true);
    assert.equal(getAccessToken(), 'new-access');
    assert.equal(getRefreshToken(), null);
  });

  it('does not dispatch duplicate expiry notifications for one expired session', () => {
    let events = 0;
    const unsubscribe = subscribeSessionExpired(() => { events += 1; });
    assert.equal(emitSessionExpired({ accessToken: 'old-access' }), true);
    assert.equal(emitSessionExpired({ accessToken: 'old-access' }), false);
    assert.equal(events, 1);
    unsubscribe();
  });

  it('ignores a definitive failure from a request belonging to an older login', async () => {
    storage.setItem('accessToken', 'old-access');
    let releaseRequest;
    let markStarted;
    const requestStarted = new Promise((resolve) => { markStarted = resolve; });
    const requestReleased = new Promise((resolve) => { releaseRequest = resolve; });

    installAdapters(
      async (config) => {
        markStarted();
        await requestReleased;
        throw rejected(config, 401);
      },
      async () => { throw new Error('refresh must not be called'); },
    );

    const request = api.get('/research/protected');
    await requestStarted;
    storage.setItem('accessToken', 'new-access');
    releaseRequest();
    await assert.rejects(request);
    assert.equal(getAccessToken(), 'new-access');
  });
});
