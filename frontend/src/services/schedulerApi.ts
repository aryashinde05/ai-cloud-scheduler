// Scheduler API service — communicates with backend scheduler endpoints
// Uses the shared axios instance so auth headers, interceptors, and retries apply.
import { api } from './api';

// Types
export interface SchedulableResource {
    instance_id: string;
    name: string;
    instance_type: string;
    state: string;
    az: string;
    avg_cpu_24h: number;
    cpu_sparkline: Array<{ timestamp: string; cpu: number }>;
    hourly_cost: number;
    monthly_cost: number;
    schedule_id: string | null;
    launch_time: string;
    resource_type?: 'ec2' | 'rds';
    do_not_schedule?: boolean;
    estimated_hourly_cost?: number;
    cost_stop_suggested?: boolean;
}

export interface ResourcesResponse {
    resources: SchedulableResource[];
    message?: string;
}

export interface HourlyProfile {
    hour: number;
    label: string;
    avg_cpu: number;
    peak_cpu: number;
    samples: number;
}

export interface IdleWindow {
    start: string;
    end: string;
    duration_hours: number;
    type: string;
}

export interface ResourceAnalysis {
    instance: {
        instance_id: string;
        name: string;
        instance_type: string;
        state: string;
    };
    analysis: {
        period: string;
        avg_cpu: number;
        max_cpu: number;
        idle_hours_per_day: number;
        idle_percentage: number;
        peak_hours: number[];
        hourly_profile: HourlyProfile[];
        idle_windows: IdleWindow[];
        idle_threshold: number;
        error?: string;
    };
    network: {
        inbound_trend: Array<{ timestamp: string; bytes: number; mb: number }>;
        outbound_trend: Array<{ timestamp: string; bytes: number; mb: number }>;
    };
    savings: {
        hourly_cost: number;
        current_monthly_cost: number;
        estimated_monthly_savings: number;
        savings_percentage: number;
    };
    suggested_schedule: {
        type: string;
        action: string;
        stop_time: string;
        start_time: string;
        idle_window: IdleWindow;
        estimated_monthly_savings: number;
        confidence: number;
        description: string;
    } | null;
}

export interface Schedule {
    id: string;
    instance_id: string;
    instance_name: string;
    instance_ids?: string[];
    schedule_type: string;
    stop_time: string;
    start_time: string;
    days: string[];
    enabled: boolean;
    estimated_monthly_savings: number;
    created_at: string;
    last_action: string | null;
    total_savings: number;
    executions: number;
    timezone?: string;
    days_pattern?: string;
    estimated_hourly_usd?: number | null;
}

export interface SavingsSummary {
    active_schedules: number;
    total_schedules: number;
    estimated_monthly_savings: number;
    estimated_annual_savings: number;
    total_realized_savings: number;
    /** Subset of total_realized_savings persisted on stop actions (DB). */
    realized_savings_logged_usd?: number;
    total_executions: number;
    actions_executed: number;
    actions_successful: number;
    actions_failed: number;
    success_rate: number;
}

export interface ActionResult {
    id: string;
    instance_id?: string;
    resource_id?: string;
    resource_type?: string;
    action: string;
    timestamp: string;
    status: string;
    message: string;
    estimated_savings_usd?: number | null;
}

export interface SchedulerSettings {
    execution_enabled: boolean;
}

export interface SmartRecommendation {
    instance_id: string;
    name: string;
    reason: string;
    suggested_stop_time: string;
    suggested_start_time: string;
    days_pattern: string;
    estimated_hourly_cost?: number;
}

// API Functions
export const schedulerApi = {
    async getResources(): Promise<ResourcesResponse> {
        const response = await api.get('/api/scheduler/resources');
        return {
            resources: response.data.resources || [],
            message: response.data.message,
        };
    },

    async analyzeResource(instanceId: string): Promise<ResourceAnalysis> {
        const response = await api.post(`/api/scheduler/analyze/${instanceId}`);
        return response.data;
    },

    async getSchedules(): Promise<Schedule[]> {
        const response = await api.get('/api/scheduler/schedules');
        return response.data.schedules || [];
    },

    async createSchedule(data: Partial<Schedule>): Promise<Schedule> {
        const response = await api.post('/api/scheduler/schedules', data);
        return response.data;
    },

    /** DB + APScheduler production schedule (cron start/stop). */
    async createProductionSchedule(payload: {
        instance_ids?: string[];
        instance_id?: string;
        start_time: string;
        stop_time: string;
        timezone?: string;
        days_pattern?: 'all' | 'weekdays' | 'weekends';
        enabled?: boolean;
        estimated_hourly_usd?: number | null;
    }): Promise<Schedule> {
        const response = await api.post('/api/scheduler/create', payload);
        return response.data.schedule;
    },

    async updateSchedule(id: string, data: Partial<Schedule>): Promise<Schedule> {
        const response = await api.put(`/api/scheduler/schedules/${id}`, data);
        return response.data;
    },

    async deleteSchedule(id: string): Promise<void> {
        await api.delete(`/api/scheduler/schedules/${id}`);
    },

    async getSavings(): Promise<SavingsSummary> {
        const response = await api.get('/api/scheduler/savings');
        return response.data;
    },

    async getSchedulerSettings(): Promise<SchedulerSettings> {
        const response = await api.get('/api/scheduler/settings');
        return response.data;
    },

    async updateSchedulerSettings(execution_enabled: boolean): Promise<SchedulerSettings> {
        const response = await api.put('/api/scheduler/settings', { execution_enabled });
        return response.data;
    },

    async getSmartRecommendations(): Promise<{ recommendations: SmartRecommendation[] }> {
        const response = await api.get('/api/scheduler/smart-recommendations');
        return response.data;
    },

    async executeAction(actionType: string, resourceId: string): Promise<ActionResult> {
        const response = await api.post('/api/scheduler/actions/execute', {
            action_type: actionType,
            resource_id: resourceId,
        });
        return response.data;
    },

    async getActionHistory(): Promise<ActionResult[]> {
        const response = await api.get('/api/scheduler/actions/history');
        return response.data.history || [];
    },
};

export default schedulerApi;
