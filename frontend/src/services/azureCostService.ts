import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

function getStoredCredentials() {
  try {
    const stored = localStorage.getItem('azure_credentials');
    return stored ? JSON.parse(stored) : {};
  } catch (e) {
    return {};
  }
}

export const azureCostService = {
  getStoredCredentials() {
    return getStoredCredentials();
  },

  async testConnection(credentials: {
    tenant_id: string;
    client_id: string;
    client_secret: string;
    subscription_id: string;
  }) {
    const response = await api.post('/api/v1/azure-cost/test-connection', credentials);
    return response.data;
  },

  async analyzeCost(payload: { days_back: number }) {
    const credentials = getStoredCredentials();
    const response = await api.post('/api/v1/azure-cost/analyze', { 
      ...credentials, 
      ...payload 
    });
    return response.data;
  },

  async getServiceBreakdown(days: number = 30) {
    const credentials = getStoredCredentials();
    const response = await api.post('/api/v1/azure-cost/service-breakdown', { 
      ...credentials,
      days
    });
    return response.data;
  },

  async getCostTrends(days: number = 30) {
    const credentials = getStoredCredentials();
    const response = await api.post('/api/v1/azure-cost/cost-trends', { 
      ...credentials,
      days
    });
    return response.data;
  },

  async getQuickWins() {
    const credentials = getStoredCredentials();
    const response = await api.post('/api/v1/azure-cost/quick-wins', credentials);
    return response.data;
  },

  async getOpportunities(type: string) {
    const credentials = getStoredCredentials();
    const response = await api.post(`/api/v1/azure-cost/opportunities/${type}`, credentials);
    return response.data;
  }
};
