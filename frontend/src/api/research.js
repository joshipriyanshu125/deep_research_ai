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

// Quick Answer — direct Gemini answer. It never starts a deep-research job.
export const quickAnswer = (query) => api.post('/v1/quick-answer', { query });

// Reports
export const getAllReports = (params) => api.get('/reports', { params });
export const getReportById = (id) => api.get(`/reports/${id}`);
export const deleteReport = (id) => api.delete(`/reports/${id}`);

// The FastAPI deployment exposes these resources below a research job, while
// the Node deployment embeds them in the job/report responses. The hook uses
// these endpoints when available and falls back to the embedded Node payload.
export const getResearchSources = (id) => api.get(`/research/${id}/sources`);
export const getResearchEvidence = (id) => api.get(`/sources/research/${id}/evidence`);

export const getReportForResearch = async (id) => {
  try {
    return await api.get(`/research/${id}/report`);
  } catch (error) {
    // Node exposes GET /reports?researchId=..., whereas FastAPI exposes the
    // resource below /research/:id/report. Keep both deployments compatible.
    if (![404, 405].includes(error.response?.status)) throw error;
    return api.get('/reports', { params: { researchId: id } });
  }
};

