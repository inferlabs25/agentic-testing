import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

api.interceptors.request.use((config) => {
  const apiKey = import.meta.env.VITE_PILOT_API_KEY;
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  config.headers['X-Actor'] = 'pilot-ui';
  return config;
});

export async function pollJob(jobId, onUpdate) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const response = await api.get(`/api/jobs/${jobId}`);
    const lastJob = response.data;
    if (onUpdate) onUpdate(lastJob);
    if (['completed', 'failed', 'cancelled'].includes(lastJob.status)) {
      return lastJob;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('Job polling timed out');
}

export default api;
