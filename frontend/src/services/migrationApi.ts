// Migration Advisor API service
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Migration Types
export interface MigrationProject {
  project_id: string;
  organization_name: string;
  created_date: string;
  status: 'ASSESSMENT' | 'ANALYSIS' | 'RECOMMENDATION' | 'PLANNING' | 'EXECUTION' | 'COMPLETE';
  current_phase: string;
  estimated_completion: string;
}

export interface OrganizationProfile {
  company_size: 'SMALL' | 'MEDIUM' | 'LARGE' | 'ENTERPRISE';
  industry: string;
  current_infrastructure: 'ON_PREMISES' | 'CLOUD' | 'HYBRID';
  geographic_presence: string[];
  it_team_size: number;
  cloud_experience_level: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
}

export interface WorkloadProfile {
  total_compute_cores: number;
  total_memory_gb: number;
  total_storage_tb: number;
  database_types: string[];
  data_volume_tb: number;
  peak_transaction_rate: number;
}

export interface PerformanceRequirements {
  latency_target_ms: number;
  availability_target: number;
  disaster_recovery_rto_minutes: number;
  disaster_recovery_rpo_minutes: number;
  geographic_distribution: string[];
}

export interface ComplianceRequirements {
  regulatory_frameworks: string[];
  data_residency_requirements: string[];
  industry_certifications: string[];
  security_standards: string[];
}

export interface BudgetConstraints {
  current_monthly_cost: number;
  migration_budget: number;
  target_monthly_cost: number;
  cost_optimization_priority: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface TechnicalRequirements {
  required_services: string[];
  ml_ai_required: boolean;
  analytics_required: boolean;
  container_orchestration: boolean;
  serverless_required: boolean;
}

export interface ProviderRecommendation {
  provider: string;
  overall_score: number;
  service_score: number;
  cost_score: number;
  compliance_score: number;
  performance_score: number;
  migration_complexity_score: number;
  strengths: string[];
  weaknesses: string[];
  estimated_monthly_cost: number;
  confidence_score: number;
}

export interface MigrationPlan {
  plan_id: string;
  project_id: string;
  target_provider?: string;
  total_duration_days?: number;
  estimated_cost?: number;
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH';
  total_phases: number;
  completed_phases: number;
  overall_progress: number;
  estimated_completion_date: string;
  actual_start_date?: string;
  phases: MigrationPhase[];
  total_cost_estimate: number;
  risks: string[];
}

export interface MigrationPhase {
  phase_id: string;
  phase_name: string;
  description: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'blocked';
  start_date?: string;
  end_date?: string;
  estimated_duration_days: number;
  progress_percentage: number;
  dependencies: string[];
  tasks: MigrationTask[];
  workload_count?: number;
}

export interface MigrationTask {
  task_id: string;
  task_name: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'failed';
  assigned_to?: string;
  estimated_hours: number;
  actual_hours?: number;
}

export interface CloudResource {
  resource_id: string;
  resource_type: string;
  resource_name: string;
  provider: string;
  region: string;
  team?: string;
  project?: string;
  environment?: string;
  cost_center?: string;
  tags: Record<string, string>;
}

export interface OrganizationalStructure {
  teams: string[];
  projects: string[];
  environments: string[];
  regions: string[];
  cost_centers: string[];
}

export interface DimensionalView {
  dimension: string;
  groups: Array<{
    group_name: string;
    resource_count: number;
    total_cost: number;
    resources: CloudResource[];
  }>;
  total_resources: number;
  total_cost: number;
}

export interface MigrationReport {
  project_id: string;
  start_date: string;
  completion_date: string;
  actual_duration_days: number;
  planned_duration_days: number;
  total_cost: number;
  budgeted_cost: number;
  resources_migrated: number;
  success_rate: number;
  cost_by_service: Record<string, number>;
  optimization_opportunities: Array<{
    type: string;
    description: string;
    estimated_savings: number;
  }>;
}

// Migration Advisor API Functions
export const migrationApi = {
  // Migration Projects
  async createProject(data: {
    organization_name: string;
  }): Promise<MigrationProject> {
    const response = await api.post('/api/migrations/projects', data);
    return response.data;
  },

  async getProject(projectId: string): Promise<MigrationProject> {
    const response = await api.get(`/api/migrations/projects/${projectId}`);
    return response.data;
  },

  async listProjects(): Promise<MigrationProject[]> {
    const response = await api.get('/api/migrations/projects');
    return response.data;
  },

  async updateProject(projectId: string, data: Partial<MigrationProject>): Promise<MigrationProject> {
    const response = await api.put(`/api/migrations/projects/${projectId}`, data);
    return response.data;
  },

  // Assessment
  async submitOrganizationProfile(
    projectId: string,
    profile: OrganizationProfile
  ): Promise<void> {
    // Backend validators expect lowercase enum values
    const payload = {
      ...profile,
      company_size: profile.company_size?.toLowerCase(),
      current_infrastructure: profile.current_infrastructure?.toLowerCase(),
      cloud_experience_level: profile.cloud_experience_level?.toLowerCase(),
    };
    await api.post(`/api/migrations/${projectId}/assessment/organization`, payload);
  },

  async submitWorkloadProfile(
    projectId: string,
    workload: WorkloadProfile
  ): Promise<void> {
    // Add required fields that the backend expects
    const workloadData = {
      workload_name: "Primary Workload",
      application_type: "Web Application",
      ...workload
    };
    await api.post(`/api/migrations/${projectId}/workloads`, workloadData);
  },

  async submitRequirements(
    projectId: string,
    requirements: {
      performance: PerformanceRequirements;
      compliance: ComplianceRequirements;
      budget: BudgetConstraints;
      technical: TechnicalRequirements;
    }
  ): Promise<void> {
    // Submit each requirement type separately as the backend expects
    // Backend expects lowercase cost_optimization_priority
    const budgetPayload = {
      ...requirements.budget,
      cost_optimization_priority: requirements.budget.cost_optimization_priority?.toLowerCase(),
    };
    // Backend PerformanceRequirementsRequest uses different field names for RTO/RPO
    const perfPayload = {
      availability_target: requirements.performance.availability_target,
      disaster_recovery_rto: requirements.performance.disaster_recovery_rto_minutes,
      disaster_recovery_rpo: requirements.performance.disaster_recovery_rpo_minutes,
      geographic_distribution: requirements.performance.geographic_distribution,
      latency_requirements: { latency_target_ms: requirements.performance.latency_target_ms },
    };
    await Promise.all([
      api.post(`/api/migrations/${projectId}/performance-requirements`, perfPayload),
      api.post(`/api/migrations/${projectId}/compliance-requirements`, requirements.compliance),
      api.post(`/api/migrations/${projectId}/budget-constraints`, budgetPayload),
      api.post(`/api/migrations/${projectId}/technical-requirements`, requirements.technical),
    ]);
  },

  async getAssessmentStatus(projectId: string): Promise<{
    organization_complete: boolean;
    workload_complete: boolean;
    requirements_complete: boolean;
    overall_progress: number;
  }> {
    try {
      // Check each component individually since there's no single status endpoint
      const [orgCheck, workloadCheck, perfCheck, complianceCheck, budgetCheck, techCheck] = await Promise.allSettled([
        api.get(`/api/migrations/${projectId}/assessment/organization`),
        api.get(`/api/migrations/${projectId}/workloads`),
        api.get(`/api/migrations/${projectId}/performance-requirements`),
        api.get(`/api/migrations/${projectId}/compliance-requirements`),
        api.get(`/api/migrations/${projectId}/budget-constraints`),
        api.get(`/api/migrations/${projectId}/technical-requirements`),
      ]);

      const organization_complete = orgCheck.status === 'fulfilled';
      const workload_complete = workloadCheck.status === 'fulfilled';
      const requirements_complete = perfCheck.status === 'fulfilled' && 
                                   complianceCheck.status === 'fulfilled' && 
                                   budgetCheck.status === 'fulfilled' && 
                                   techCheck.status === 'fulfilled';

      let overall_progress = 0;
      if (organization_complete) overall_progress += 33;
      if (workload_complete) overall_progress += 33;
      if (requirements_complete) overall_progress += 34;

      return {
        organization_complete,
        workload_complete,
        requirements_complete,
        overall_progress
      };
    } catch (error) {
      // Return default status if checks fail
      return {
        organization_complete: false,
        workload_complete: false,
        requirements_complete: false,
        overall_progress: 0
      };
    }
  },

  // Recommendations
  async generateRecommendations(projectId: string, requirementsData?: any): Promise<ProviderRecommendation[]> {
    // Backend requires required_services and target_monthly_budget in the body
    const body = {
      required_services: requirementsData?.technical?.required_services || ['Compute', 'Storage', 'Database'],
      target_monthly_budget: requirementsData?.budget?.target_monthly_cost || 4000,
      compliance_requirements: requirementsData?.compliance?.regulatory_frameworks || [],
      source_infrastructure: 'on_premises',
      providers: ['aws', 'gcp', 'azure'],
    };
    const response = await api.post(`/api/migrations/${projectId}/recommendations/generate`, body);
    
    // Handle new response format with metadata
    if (response.data.recommendations) {
      return response.data.recommendations;
    }
    if (response.data.primary_recommendation) {
      // Convert RecommendationReportResponse to ProviderRecommendation[]
      const report = response.data;
      return [
        {
          provider: report.primary_recommendation.provider,
          overall_score: report.primary_recommendation.overall_score,
          service_score: report.primary_recommendation.overall_score,
          cost_score: report.primary_recommendation.overall_score,
          compliance_score: report.primary_recommendation.overall_score,
          performance_score: report.primary_recommendation.overall_score,
          migration_complexity_score: report.primary_recommendation.overall_score,
          strengths: report.primary_recommendation.strengths,
          weaknesses: report.primary_recommendation.weaknesses,
          estimated_monthly_cost: report.primary_recommendation.estimated_monthly_cost || 0,
          confidence_score: report.primary_recommendation.confidence_score,
        },
        ...report.alternative_recommendations.map((alt: any) => ({
          provider: alt.provider,
          overall_score: alt.overall_score,
          service_score: alt.overall_score,
          cost_score: alt.overall_score,
          compliance_score: alt.overall_score,
          performance_score: alt.overall_score,
          migration_complexity_score: alt.overall_score,
          strengths: alt.strengths,
          weaknesses: alt.weaknesses,
          estimated_monthly_cost: alt.estimated_monthly_cost || 0,
          confidence_score: alt.confidence_score,
        })),
      ];
    }
    // Fallback for old response format
    return Array.isArray(response.data) ? response.data : [];
  },

  async getRecommendations(projectId: string): Promise<ProviderRecommendation[]> {
    const response = await api.get(`/api/migrations/${projectId}/recommendations`);
    
    // Handle response format (could be array or object with recommendations)
    if (Array.isArray(response.data)) {
      return response.data;
    } else if (response.data.recommendations) {
      return response.data.recommendations;
    }
    
    return response.data;
  },

  async checkRecommendationsExist(projectId: string): Promise<boolean> {
    try {
      const recommendations = await this.getRecommendations(projectId);
      return recommendations && recommendations.length > 0;
    } catch (error) {
      return false;
    }
  },

  async updateWeights(
    projectId: string,
    weights: {
      service_weight: number;
      cost_weight: number;
      compliance_weight: number;
      performance_weight: number;
      migration_complexity_weight: number;
    }
  ): Promise<ProviderRecommendation[]> {
    const response = await api.put(`/api/migrations/${projectId}/recommendations/weights`, weights);
    return response.data;
  },

  async getProviderComparison(projectId: string): Promise<{
    providers: string[];
    comparison_matrix: Record<string, any>;
  }> {
    const response = await api.get(`/api/migrations/${projectId}/recommendations/comparison`);
    return response.data;
  },

  // Migration Planning
  async generateMigrationPlan(
    projectId: string,
    selectedProvider: string
  ): Promise<MigrationPlan> {
    const response = await api.post(`/api/migrations/${projectId}/plan`, {
      selected_provider: selectedProvider,
    });
    return response.data;
  },

  async getMigrationPlan(projectId: string): Promise<MigrationPlan> {
    const response = await api.get(`/api/migrations/${projectId}/plan`);
    return response.data;
  },

  async updatePhaseStatus(
    projectId: string,
    phaseId: string,
    status: string
  ): Promise<void> {
    await api.put(`/api/migrations/${projectId}/plan/phases/${phaseId}/status`, { status });
  },

  async getMigrationProgress(projectId: string): Promise<{
    overall_progress: number;
    phases_completed: number;
    total_phases: number;
    current_phase: string;
  }> {
    const response = await api.get(`/api/migrations/${projectId}/plan/progress`);
    return response.data;
  },

  // Resource Organization
  async discoverResources(
    projectId: string,
    provider: string,
    credentials: any
  ): Promise<CloudResource[]> {
    const response = await api.post(`/api/migrations/${projectId}/resources/discover`, {
      provider,
      credentials,
    });
    return response.data;
  },

  async organizeResources(
    projectId: string,
    structure: OrganizationalStructure
  ): Promise<void> {
    await api.post(`/api/migrations/${projectId}/resources/organize`, structure);
  },

  async getResources(projectId: string): Promise<CloudResource[]> {
    const response = await api.get(`/api/migrations/${projectId}/resources`);
    return response.data;
  },

  async categorizeResource(
    projectId: string,
    resourceId: string,
    categorization: {
      team?: string;
      project?: string;
      environment?: string;
      cost_center?: string;
    }
  ): Promise<void> {
    await api.put(`/api/migrations/${projectId}/resources/${resourceId}/categorize`, categorization);
  },

  // Dimensional Management
  async createDimension(
    dimensionType: string,
    data: any
  ): Promise<void> {
    await api.post('/api/organizations/dimensions', {
      dimension_type: dimensionType,
      data,
    });
  },

  async getDimensions(dimensionType: string): Promise<any[]> {
    const response = await api.get(`/api/organizations/dimensions/${dimensionType}`);
    return response.data;
  },

  async getDimensionalView(dimension: string, filters?: any): Promise<DimensionalView> {
    const response = await api.get(`/api/resources/views/${dimension}`, { params: filters });
    return response.data;
  },

  async filterResources(filterExpression: any): Promise<CloudResource[]> {
    const response = await api.post('/api/resources/filter', filterExpression);
    return response.data;
  },

  // Integration & Reports
  async integrateFinOps(projectId: string): Promise<void> {
    await api.post(`/api/migrations/${projectId}/integration/finops`);
  },

  async captureBaselines(projectId: string): Promise<void> {
    await api.post(`/api/migrations/${projectId}/integration/baselines`);
  },

  async getMigrationReport(projectId: string): Promise<MigrationReport> {
    const response = await api.get(`/api/migrations/${projectId}/reports/final`);
    return response.data;
  },

  // Additional methods for new UI components
  async getOrganizationalStructure(projectId: string): Promise<OrganizationalStructure> {
    const response = await api.get(`/api/migrations/${projectId}/resources/structure`);
    return response.data;
  },

  async getResourceHierarchy(projectId: string): Promise<any[]> {
    const response = await api.get(`/api/migrations/${projectId}/resources/hierarchy`);
    return response.data;
  },

  async categorizeResources(
    projectId: string,
    resourceIds: string[],
    categorization: {
      category?: string;
      team?: string;
      project?: string;
    }
  ): Promise<void> {
    await api.post(`/api/migrations/${projectId}/resources/categorize-bulk`, {
      resource_ids: resourceIds,
      categorization,
    });
  },

  async generateInventoryReport(projectId: string, config: any): Promise<any> {
    const response = await api.post(`/api/migrations/${projectId}/reports/inventory`, config);
    return response.data;
  },

  // Scenario Management and Regeneration Features
  async getScenarioHistory(projectId: string): Promise<{
    scenarios: Array<{
      scenario_id: string;
      timestamp: string;
      type: string;
      description: string;
      recommendation_count: number;
      top_provider: string;
      top_score: number;
      weights?: any;
    }>;
  }> {
    const response = await api.get(`/api/migrations/${projectId}/scenarios`);
    return response.data;
  },

  async getScenarioDetails(projectId: string, scenarioId: string): Promise<any> {
    const response = await api.get(`/api/migrations/${projectId}/scenarios/${scenarioId}`);
    return response.data;
  },

  async activateScenario(projectId: string, scenarioId: string): Promise<any> {
    const response = await api.post(`/api/migrations/${projectId}/scenarios/${scenarioId}/activate`);
    return response.data;
  },

  async compareScenarios(projectId: string, scenarioIds: string[]): Promise<any> {
    const response = await api.post(`/api/migrations/${projectId}/scenarios/compare`, {
      scenario_ids: scenarioIds
    });
    return response.data;
  },

  async modifyAssessmentAndRegenerate(
    projectId: string,
    modifications: {
      organization?: any;
      workload?: any;
      requirements?: any;
    }
  ): Promise<{
    message: string;
    modifications_applied: string[];
    recommendations: ProviderRecommendation[];
    scenario_id: string;
  }> {
    const response = await api.put(`/api/migrations/${projectId}/assessment/modify`, modifications);
    return response.data;
  },
};

export default migrationApi;
