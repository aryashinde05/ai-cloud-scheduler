import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export const awsService = {
  async connect(credentials: { access_key: string; secret_key: string; region: string }) {
    const response = await api.post('/api/v1/aws/connect', credentials);
    return response.data;
  },

  async getStatus() {
    const response = await api.get('/api/v1/aws/status');
    return response.data;
  },

  async getResources() {
    const response = await api.get('/api/v1/aws/resources');
    return response.data;
  }
};
