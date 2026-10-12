
import api from './axios.js';

export const register = (data) => api.post('/auth/register', data);
export const login = (data) => api.post('/auth/login', data);
export const logout = () => api.post('/auth/logout');
export const refresh = (refreshToken) => api.post('/auth/refresh', { refreshToken });
export const getMe = (config) => api.get('/auth/me', config);
export const forgotPassword = (email) => api.post('/auth/forgot-password', { email });
export const resetPassword = (data) => api.post('/auth/reset-password', data);
