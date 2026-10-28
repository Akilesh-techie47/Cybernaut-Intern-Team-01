import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.message || error.message || 'An error occurred';
    return Promise.reject({ message, status: error.response?.status, data: error.response?.data });
  }
);

export const healthApi = {
  check: () => api.get('/health'),
};

export const productsApi = {
  getAll: (params) => api.get('/products', { params }),
  getById: (id) => api.get(`/products/${id}`),
  getReviews: (id, params) => api.get(`/products/${id}/reviews`, { params }),
  getSentiment: (id) => api.get(`/products/${id}/sentiment`),
  getTrends: (id, params) => api.get(`/products/${id}/trends`, { params }),
  getKeywords: (id) => api.get(`/products/${id}/keywords`),
  delete: (id) => api.delete(`/products/${id}`),
};

export const scrapingApi = {
  // Live Selenium scraping can take 60-120s, so allow a long timeout for this call only.
  scrape: (data) => api.post('/scrape', data, { timeout: 180000 }),
  getSources: () => api.get('/scrape/sources'),
};

export const statsApi = {
  getGlobal: () => api.get('/stats'),
};

export default api;