import { api } from './api';

export interface AsgScalingRuleCreate {
    asg_name: string;
    min_size: number;
    max_size: number;
    scale_up_cpu?: number;
    scale_down_cpu?: number;
    region?: string;
}

export interface AsgScalingRuleRow {
    public_id: string;
    asg_name: string;
    region: string;
    min_size: number;
    max_size: number;
    scale_up_cpu: number;
    scale_down_cpu: number;
    alarm_high_name?: string | null;
    alarm_low_name?: string | null;
}

export const autoscalingAsgApi = {
    async createRule(body: AsgScalingRuleCreate) {
        const res = await api.post('/autoscaling/create-rule', body);
        return res.data;
    },

    async listRules(): Promise<{ rules: AsgScalingRuleRow[]; total: number }> {
        const res = await api.get('/autoscaling/rules');
        return res.data;
    },

    async deleteRule(publicId: string) {
        const res = await api.delete(`/autoscaling/delete-rule/${publicId}`);
        return res.data;
    },

    async applyRule(publicId: string) {
        const res = await api.post(`/autoscaling/apply-rule/${publicId}`);
        return res.data;
    },
};

export default autoscalingAsgApi;
