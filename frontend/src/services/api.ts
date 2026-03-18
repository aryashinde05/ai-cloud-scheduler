// API service for FinOps Platform
import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { ErrorMessageFormatter, APICallLogger } from '../utils/errorHandler';
import { retryWithBackoff, retryWithRateLimit, DEFAULT_RETRY_CONFIG } from '../utils/retryLogic';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Cache for storing API responses
const apiCache = new Map<string, { data: any; timestamp: number; ttl: number }>();

// Cache TTL in milliseconds (5 minutes)
const DEFAULT_CACHE_TTL = 5 * 60 * 1000;

/**
 * Generate cache key from request config
 */
function getCacheKey(url: string, params?: any): string {
  const paramString = params ? JSON.stringify(params) : '';
  return `${url}:${paramString}`;
}

/**
 * Get data from cache if valid
 */
function getFromCache(key: string): any | null {
  const cached = apiCache.get(key);
  if (!cached) return null;

  const now = Date.now();
  if (now - cached.timestamp > cached.ttl) {
    apiCache.delete(key);
    return null;
  }

  console.log(`[Cache] Hit for ${key}`);
  return cached.data;
}

/**
 * Store data in cache
 */
function setCache(key: string, data: any, ttl: number = DEFAULT_CACHE_TTL) {
  apiCache.set(key, {
    data,
    timestamp: Date.now(),
    ttl,
  });
  console.log(`[Cache] Stored ${key} with TTL ${ttl}ms`);
}

/**
 * Clear cache entries matching pattern
 */
function clearCachePattern(pattern: string) {
  const keys = Array.from(apiCache.keys());
  keys.forEach(key => {
    if (key.includes(pattern)) {
      apiCache.delete(key);
    }
  });
}

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    const startTime = Date.now();
    (config as any).startTime = startTime;
    
    APICallLogger.logRequest(
      config.method?.toUpperCase() || 'GET',
      config.url || ''
    );
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for logging and error handling
api.interceptors.response.use(
  (response) => {
    const config = response.config as any;
    const duration = Date.now() - (config.startTime || 0);
    
    APICallLogger.logResponse(
      config.method?.toUpperCase() || 'GET',
      config.url || '',
      response.status,
      config.startTime || Date.now()
    );
    
    return response;
  },
  (error: AxiosError) => {
    const config = error.config as any;
    
    if (config) {
      APICallLogger.logError(
        config.method?.toUpperCase() || 'GET',
        config.url || '',
        error.message,
        config.startTime || Date.now()
      );
    }
    
    return Promise.reject(error);
  }
);

/**
 * Make API request with retry logic and cache fallback
 * Validates: Requirements 4.1, 4.2, 4.4
 */
async function makeRequest<T>(
  requestFn: () => Promise<T>,
  cacheKey?: string,
  cacheTTL: number = DEFAULT_CACHE_TTL
): Promise<T> {
  try {
    // Try to get from cache first
    if (cacheKey) {
      const cached = getFromCache(cacheKey);
      if (cached !== null) {
        return cached;
      }
    }

    // Make request with retry logic
    const response = await retryWithBackoff(
      requestFn,
      DEFAULT_RETRY_CONFIG,
      (attempt, error) => {
        console.log(`Retrying request (attempt ${attempt}):`, error.message);
      }
    );

    // Cache successful response
    if (cacheKey) {
      setCache(cacheKey, response, cacheTTL);
    }

    return response;
  } catch (error: any) {
    // Format error for user display
    const formattedError = ErrorMessageFormatter.formatError(error);
    
    console.error('API request failed:', formattedError);

    // Try to use cached data as fallback
    if (cacheKey && formattedError.fallbackAvailable) {
      const cached = apiCache.get(cacheKey);
      if (cached) {
        console.warn('Using stale cached data as fallback');
        return cached.data;
      }
    }

    // Throw formatted error
    throw formattedError;
  }
}

// FinOps Types
export interface CostData {
  date: string;
  service: string;
  team: string;
  cost: number;
  usage_quantity: number;
  usage_unit: string;
}

export interface Budget {
  id: string;
  name: string;
  amount: number;
  spent: number;
  utilization: number;
  period: string;
  status: string;
  team: string;
  alerts: Array<{
    threshold: number;
    triggered: boolean;
  }>;
}

export interface OptimizationRecommendation {
  id: string;
  type: string;
  resource: string;
  resourceType: string;
  currentConfig: string;
  recommendedConfig: string;
  monthlySavings: number;
  annualSavings: number;
  confidence: number;
  riskLevel: string;
  status: string;
  team: string;
}

export interface Alert {
  id: string;
  name: string;
  type: string;
  condition: string;
  threshold: number;
  currentValue: number;
  status: string;
  severity: string;
  enabled: boolean;
  channels: string[];
  team: string;
}

export interface ComplianceData {
  overallScore: number;
  taggingCompliance: number;
  policyCompliance: number;
  securityCompliance: number;
  violations: Array<{
    id: string;
    resource: string;
    policy: string;
    violation: string;
    severity: string;
    status: string;
  }>;
}

// FinOps API Functions
export const apiService = {
  // Health check
  async healthCheck() {
    const response = await api.get('/health');
    return response.data;
  },

  // Cost Management
  async getCosts(params: {
    startDate: string;
    endDate: string;
    granularity?: string;
    groupBy?: string[];
    filters?: any;
  }): Promise<{ data: CostData[]; total: number }> {
    const cacheKey = getCacheKey('/api/v1/costs', params);
    return makeRequest(
      async () => {
        const response = await api.get('/api/v1/costs', { params });
        return response.data;
      },
      cacheKey,
      DEFAULT_CACHE_TTL
    );
  },

  async getCostAttribution(params: {
    startDate: string;
    endDate: string;
    dimension: string;
  }) {
    const cacheKey = getCacheKey('/api/v1/costs/attribution', params);
    return makeRequest(
      async () => {
        const response = await api.get('/api/v1/costs/attribution', { params });
        return response.data;
      },
      cacheKey,
      DEFAULT_CACHE_TTL
    );
  },

  async getCostAnomalies(params?: {
    startDate?: string;
    endDate?: string;
    confidenceThreshold?: number;
  }) {
    const cacheKey = getCacheKey('/api/v1/costs/anomalies', params);
    return makeRequest(
      async () => {
        const response = await api.get('/api/v1/costs/anomalies', { params });
        return response.data;
      },
      cacheKey,
      DEFAULT_CACHE_TTL
    );
  },

  // Budget Management
  async getBudgets(params?: { status?: string; team?: string }): Promise<Budget[]> {
    const cacheKey = getCacheKey('/api/v1/budgets', params);
    return makeRequest(
      async () => {
        const response = await api.get('/api/v1/budgets', { params });
        return response.data.budgets;
      },
      cacheKey,
      DEFAULT_CACHE_TTL
    );
  },

  async createBudget(budget: Omit<Budget, 'id'>): Promise<Budget> {
    const response = await api.post('/api/v1/budgets', budget);
    clearCachePattern('/api/v1/budgets');
    return response.data;
  },

  async updateBudget(id: string, budget: Partial<Budget>): Promise<Budget> {
    const response = await api.patch(`/api/v1/budgets/${id}`, budget);
    clearCachePattern('/api/v1/budgets');
    return response.data;
  },

  async deleteBudget(id: string): Promise<void> {
    await api.delete(`/api/v1/budgets/${id}`);
    clearCachePattern('/api/v1/budgets');
  },

  // Optimization
  async getOptimizationRecommendations(params?: {
    type?: string;
    minSavings?: number;
    confidence?: string;
  }): Promise<OptimizationRecommendation[]> {
    const cacheKey = getCacheKey('/api/v1/optimization/recommendations', params);
    return makeRequest(
      async () => {
        const response = await api.get('/api/v1/optimization/recommendations', { params });
        return response.data.recommendations;
      },
      cacheKey,
      DEFAULT_CACHE_TTL
    );
  },

  async implementRecommendation(id: string, params: {
    implementationDate?: string;
    notes?: string;
  }): Promise<void> {
    await api.post(`/api/v1/optimization/recommendations/${id}/implement`, params);
  },

  async getRIRecommendations() {
    const response = await api.get('/api/v1/optimization/reserved-instances');
    return response.data;
  },

  // Reports
  async generateReport(params: {
    type: string;
    name: string;
    parameters: any;
    format: string;
    delivery?: any;
  }) {
    const response = await api.post('/api/v1/reports/generate', params);
    return response.data;
  },

  async getReports() {
    const response = await api.get('/api/v1/reports');
    return response.data;
  },

  async getReportStatus(id: string) {
    const response = await api.get(`/api/v1/reports/${id}`);
    return response.data;
  },

  async downloadReport(id: string) {
    const response = await api.get(`/api/v1/reports/${id}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Alerts
  async getAlerts(): Promise<Alert[]> {
    const response = await api.get('/api/v1/alerts');
    return response.data.alerts;
  },

  async createAlert(alert: Omit<Alert, 'id'>): Promise<Alert> {
    const response = await api.post('/api/v1/alerts', alert);
    return response.data;
  },

  async updateAlert(id: string, alert: Partial<Alert>): Promise<Alert> {
    const response = await api.patch(`/api/v1/alerts/${id}`, alert);
    return response.data;
  },

  async deleteAlert(id: string): Promise<void> {
    await api.delete(`/api/v1/alerts/${id}`);
  },

  async testAlert(id: string): Promise<void> {
    await api.post(`/api/v1/alerts/${id}/test`);
  },

  // Compliance
  async getComplianceOverview(): Promise<ComplianceData> {
    const cacheKey = getCacheKey('/api/v1/compliance/overview');
    return makeRequest(
      async () => {
        const response = await api.get('/api/v1/compliance/overview');
        return response.data;
      },
      cacheKey,
      DEFAULT_CACHE_TTL
    );
  },

  async getTaggingCompliance() {
    const response = await api.get('/api/v1/compliance/tagging');
    return response.data;
  },

  async getPolicyViolations() {
    const response = await api.get('/api/v1/compliance/violations');
    return response.data;
  },

  // Configuration
  async getCloudProviders() {
    const response = await api.get('/api/v1/config/cloud-providers');
    return response.data;
  },

  async updateNotificationSettings(settings: any) {
    const response = await api.put('/api/v1/config/notifications', settings);
    return response.data;
  },

  // Webhooks
  async createWebhook(webhook: any) {
    const response = await api.post('/api/v1/webhooks', webhook);
    return response.data;
  },

  async getWebhooks() {
    const response = await api.get('/api/v1/webhooks');
    return response.data;
  },
};

export default apiService;