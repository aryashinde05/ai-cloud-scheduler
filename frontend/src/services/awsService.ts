import { api } from './api';

export interface AwsCredentials {
  access_key: string;
  secret_key: string;
  region: string;
}

export interface AwsStatus {
  connected: boolean;
  region: string | null;
}

const extractError = (err: any): string =>
  err?.response?.data?.detail || err?.response?.data?.message || err?.message || 'Unknown error';

export const awsService = {
  async connect(credentials: AwsCredentials) {
    try {
      const response = await api.post('/api/v1/aws/connect', credentials);
      return response.data;
    } catch (err: any) {
      throw new Error(extractError(err));
    }
  },

  async getStatus(): Promise<AwsStatus> {
    try {
      const response = await api.get('/api/v1/aws/status');
      return response.data;
    } catch (err: any) {
      return { connected: false, region: null };
    }
  },

  async disconnect() {
    try {
      const response = await api.delete('/api/v1/aws/disconnect');
      return response.data;
    } catch (err: any) {
      throw new Error(extractError(err));
    }
  },

  async getResources() {
    try {
      const response = await api.get('/api/v1/aws/resources');
      return response.data;
    } catch (err: any) {
      throw new Error(extractError(err));
    }
  },

  async getDashboard() {
    try {
      const response = await api.get('/api/v1/aws/dashboard');
      return response.data;
    } catch (err: any) {
      // Return empty summary on failure — dashboard handles gracefully
      return { finops_summary: null };
    }
  },
};
