import { api } from './api';

export interface CostExplorerDailyPoint {
    date: string;
    amount_usd: number;
}

export interface CostExplorerServiceRow {
    service: string;
    amount_usd: number;
}

export interface CostExplorerOverview {
    period_start: string | null;
    period_end: string | null;
    granularity_days: number;
    total_cost_usd: number;
    daily: CostExplorerDailyPoint[];
    by_service: CostExplorerServiceRow[];
    credential_source?: string | null;
    error?: string | null;
}

export const costExplorerApi = {
    async getOverview(days = 30): Promise<CostExplorerOverview> {
        const res = await api.get('/api/cost-explorer/overview', { params: { days } });
        return res.data;
    },
};

export default costExplorerApi;
