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
}

export interface SavingsSummary {
    active_schedules: number;
    total_schedules: number;
    estimated_monthly_savings: number;
    estimated_annual_savings: number;
    total_realized_savings: number;
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
}

// API Functions
export const schedulerApi = {
    // Resources
    async getResources(): Promise<SchedulableResource[]> {
        const response = await api.get('/api/scheduler/resources');
        return response.data.resources || [];
    },

    // Analysis
    async analyzeResource(instanceId: string): Promise<ResourceAnalysis> {
        const response = await api.post(`/api/scheduler/analyze/${instanceId}`);
        return response.data;
    },

    // Schedules
    async getSchedules(): Promise<Schedule[]> {
        const response = await api.get('/api/scheduler/schedules');
        return response.data.schedules || [];
    },

    async createSchedule(data: Partial<Schedule>): Promise<Schedule> {
        const response = await api.post('/api/scheduler/schedules', data);
        return response.data;
    },

    async updateSchedule(id: string, data: Partial<Schedule>): Promise<Schedule> {
        const response = await api.put(`/api/scheduler/schedules/${id}`, data);
        return response.data;
    },

    async deleteSchedule(id: string): Promise<void> {
        await api.delete(`/api/scheduler/schedules/${id}`);
    },

    // Savings
    async getSavings(): Promise<SavingsSummary> {
        const response = await api.get('/api/scheduler/savings');
        return response.data;
    },

    // Actions
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
