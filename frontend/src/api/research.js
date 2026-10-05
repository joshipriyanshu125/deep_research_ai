import api from './axios';

// Research Jobs
export const createResearch = (data) => api.post('/research', data);
export const getAllResearch = () => api.get('/research');
export const getResearchById = (id) => api.get(`/research/${id}`);
export const updateResearch = (id, data) => api.put(`/research/${id}`, data);
export const deleteResearch = (id) => api.delete(`/research/${id}`);
export const cancelResearch = (id) => api.post(`/research/${id}/cancel`);
export const resumeResearch = (id) => api.post(`/research/${id}/resume`);
export const retryResearch = (id) => api.post(`/research/${id}/retry`);

// Quick Answer — query router (simple question → Gemini direct, complex → deep pipeline)
export const quickAnswer = (query) => api.post('/v1/quick-answer', { query });
export const classifyQuery = (q) => api.get('/v1/quick-answer/classify', { params: { q } });

// Reports
export const getAllReports = (params) => api.get('/reports', { params });
export const getReportById = (id) => api.get(`/reports/${id}`);
export const deleteReport = (id) => api.delete(`/reports/${id}`);

