import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

export const getLeaderboard = (examId, page = 1, perPage = 50, userId = null) => {
  const params = { exam_id: examId, page, per_page: perPage };
  if (userId) params.user_id = userId;
  return api.get('/leaderboard', { params });
};

export const getAnalyticsLeaderboard = (examId, page = 1, perPage = 50) =>
  api.get('/analytics/leaderboard', { params: { exam_id: examId, page, per_page: perPage } });

export const getAnalyticsSummary = (examId) =>
  api.get('/analytics/summary', { params: { exam_id: examId } });

export const getAnalyticsDistribution = (examId) =>
  api.get('/analytics/distribution', { params: { exam_id: examId } });

export const getAnalyticsModules = (examId, sort = 'points_per_minute') =>
  api.get('/analytics/modules', { params: { exam_id: examId, sort } });

export const getStudentAnalytics = (userId, examId) =>
  api.get(`/analytics/student/${userId}`, { params: { exam_id: examId } });

export const submitScore = (payload) => api.post('/scores', payload);

export const createSession = (examId, userId) =>
  api.post('/sessions', { exam_id: examId, user_id: userId });

export const finishSession = (sessionId) =>
  api.patch(`/sessions/${sessionId}/finish`);

export default api;
