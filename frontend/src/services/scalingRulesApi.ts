// Scaling Rules API service — communicates with backend scaling-rules endpoints
// Uses the shared axios instance so auth headers, interceptors, and retries apply.
import { api } from './api';

// ── Types ──────────────────────────────────────────────

export interface ScalingRule {
    id: string;
    name: string;
    description: string;
    service_type: string; // ec2, ebs, rds, asg
    resource_filter: Record<string, any>;
    metric_namespace: string;
    metric_name: string;
    metric_dimension_name: string;
    metric_statistic: string;
    threshold_operator: string; // gt, lt, gte, lte
    threshold_value: number;
    evaluation_periods: number;
    evaluation_interval_seconds: number;
    scaling_direction: string; // scale_up, scale_down
    scaling_action: Record<string, any>;
    max_scaling_limit: Record<string, any>;
    cooldown_seconds: number;
    is_enabled: boolean;
    last_triggered_at: string | null;
    trigger_count: number;
    total_cost_impact: number;
    created_at: string;
    updated_at: string;
}

export interface ScalingRuleCreate {
    name: string;
    description?: string;
    service_type: string;
    resource_filter?: Record<string, any>;
    metric_namespace: string;
    metric_name: string;
    metric_dimension_name: string;
    metric_statistic?: string;
    threshold_operator: string;
    threshold_value: number;
    evaluation_periods?: number;
    evaluation_interval_seconds?: number;
    scaling_direction?: string;
    scaling_action: Record<string, any>;
    max_scaling_limit?: Record<string, any>;
    cooldown_seconds?: number;
    is_enabled?: boolean;
}

export interface RuleExecution {
    id: string;
    rule_id: string;
    rule_name: string;
    resource_id: string;
    triggered_at: string;
    metric_value_at_trigger: number;
    threshold_value: number;
    action_taken: Record<string, any>;
    previous_state: Record<string, any>;
    new_state: Record<string, any>;
    status: string;
    error_message: string | null;
    cost_impact: number | null;
    execution_duration_ms: number | null;
}

export interface ScalingStats {
    total_rules: number;
    active_rules: number;
    total_executions: number;
    successful_executions: number;
    failed_executions: number;
    total_cost_impact: number;
    success_rate: number;
}

// ── API Functions ──────────────────────────────────────

export const scalingRulesApi = {
    // Rules CRUD
    async getRules(): Promise<ScalingRule[]> {
        const response = await api.get('/api/v1/scaling-rules');
        return response.data.rules || [];
    },

    async getRule(id: string): Promise<ScalingRule> {
        const response = await api.get(`/api/v1/scaling-rules/${id}`);
        return response.data.rule;
    },

    async createRule(data: ScalingRuleCreate): Promise<ScalingRule> {
        const response = await api.post('/api/v1/scaling-rules', data);
        return response.data.rule;
    },

    async updateRule(id: string, data: Partial<ScalingRuleCreate>): Promise<ScalingRule> {
        const response = await api.put(`/api/v1/scaling-rules/${id}`, data);
        return response.data.rule;
    },

    async deleteRule(id: string): Promise<void> {
        await api.delete(`/api/v1/scaling-rules/${id}`);
    },

    async toggleRule(id: string): Promise<ScalingRule> {
        const response = await api.post(`/api/v1/scaling-rules/${id}/toggle`);
        return response.data.rule;
    },

    // Execution
    async testRule(id: string): Promise<any> {
        const response = await api.post(`/api/v1/scaling-rules/${id}/test`);
        return response.data;
    },

    async evaluateAll(): Promise<any> {
        const response = await api.post('/api/v1/scaling-rules/evaluate');
        return response.data;
    },

    // History
    async getExecutions(ruleId: string): Promise<RuleExecution[]> {
        const response = await api.get(`/api/v1/scaling-rules/${ruleId}/executions`);
        return response.data.executions || [];
    },

    async getAllExecutions(): Promise<RuleExecution[]> {
        const response = await api.get('/api/v1/scaling-rules/executions/all');
        return response.data.executions || [];
    },

    // Stats
    async getStats(): Promise<ScalingStats> {
        const response = await api.get('/api/v1/scaling-rules/stats');
        return response.data;
    },
};

export default scalingRulesApi;
