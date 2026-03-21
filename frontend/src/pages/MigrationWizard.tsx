import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Button,
  Typography,
  Paper,
  Container,
  LinearProgress,
  Grid,
  Divider,
  Card,
  CardContent,
  Chip,
  Alert,
  AppBar,
  Toolbar,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import OrganizationProfileForm from '../components/MigrationWizard/OrganizationProfileForm';
import WorkloadProfileForm from '../components/MigrationWizard/WorkloadProfileForm';
import RequirementsForm from '../components/MigrationWizard/RequirementsForm';

const STORAGE_KEY = 'migration_wizard_data';

const steps = [
  'Organization Profile',
  'Infrastructure',
  'Requirements',
  'Recommendation',
];

const defaultOrgData = {
  company_size: 'MEDIUM',
  industry: 'Technology',
  current_infrastructure: 'ON_PREMISES',
  geographic_presence: ['North America'],
  it_team_size: 10,
  cloud_experience_level: 'BEGINNER',
};

const defaultWorkloadData = {
  total_compute_cores: 4,
  total_memory_gb: 16,
  total_storage_tb: 1,
  database_types: [],
  data_volume_tb: 0.5,
  peak_transaction_rate: 100,
  physical_servers: 2,
  power_consumption_watts: 500,
  hardware_age_years: 3,
  storage_type: 'HDD',
};

const defaultRequirementsData = {
  performance: {
    latency_target_ms: 100,
    availability_target: 99.9,
    disaster_recovery_rto_minutes: 60,
    disaster_recovery_rpo_minutes: 15,
    geographic_distribution: [],
  },
  compliance: {
    regulatory_frameworks: [],
    data_residency_requirements: [],
    industry_certifications: [],
    security_standards: [],
  },
  budget: {
    current_monthly_cost: 5000,
    migration_budget: 50000,
    target_monthly_cost: 4000,
    cost_optimization_priority: 'MEDIUM',
  },
  technical: {
    required_services: ['Compute', 'Storage', 'Database'],
    ml_ai_required: false,
    analytics_required: false,
    container_orchestration: false,
    serverless_required: false,
  },
};

// ── Scoring engine ──────────────────────────────────────────────────────────

function scoreProviders(org: any, workload: any, req: any): Record<string, number> {
  const scores: Record<string, number> = { AWS: 0, Azure: 0, GCP: 0 };

  // Industry
  if (['Technology', 'Retail', 'Media'].includes(org?.industry)) {
    scores.AWS += 2; scores.GCP += 1;
  } else if (['Finance', 'Healthcare'].includes(org?.industry)) {
    scores.Azure += 2; scores.AWS += 1;
  } else if (org?.industry === 'Government') {
    scores.Azure += 3; scores.AWS += 1;
  } else {
    scores.AWS += 1; scores.Azure += 1; scores.GCP += 1;
  }

  // Company size
  if (['ENTERPRISE', 'LARGE'].includes(org?.company_size)) {
    scores.AWS += 2; scores.Azure += 2;
  } else if (org?.company_size === 'MEDIUM') {
    scores.AWS += 1; scores.GCP += 2;
  } else {
    scores.GCP += 2; scores.AWS += 1;
  }

  // Technical needs
  if (req?.technical?.ml_ai_required) { scores.GCP += 3; scores.AWS += 2; scores.Azure += 1; }
  if (req?.technical?.analytics_required) { scores.GCP += 2; scores.AWS += 2; scores.Azure += 1; }
  if (req?.technical?.container_orchestration) { scores.GCP += 2; scores.AWS += 1; scores.Azure += 1; }
  if (req?.technical?.serverless_required) { scores.AWS += 2; scores.Azure += 1; scores.GCP += 1; }

  // Compliance
  const complianceCount = req?.compliance?.regulatory_frameworks?.length || 0;
  if (complianceCount > 0) { scores.Azure += 2; scores.AWS += 2; scores.GCP += 1; }

  // Cost priority
  if (req?.budget?.cost_optimization_priority === 'HIGH') {
    scores.GCP += 2; scores.AWS += 1;
  }

  // Geography
  const regions: string[] = org?.geographic_presence || [];
  if (regions.includes('Europe')) scores.Azure += 1;
  if (regions.includes('Asia Pacific')) { scores.AWS += 1; scores.GCP += 1; }

  // Migration tooling bonus (PRD: AWS 9★, Azure 9★, GCP 7★)
  scores.AWS += 9; scores.Azure += 9; scores.GCP += 7;

  return scores;
}

// ── Migration complexity ────────────────────────────────────────────────────

function getMigrationComplexity(workload: any, req: any): {
  level: 'Low' | 'Medium' | 'High';
  timeline: string;
  color: 'success' | 'warning' | 'error';
  reasons: string[];
} {
  let score = 0;
  const reasons: string[] = [];

  const servers = Number(workload?.physical_servers) || 0;
  const dataTb = Number(workload?.data_volume_tb) || 0;
  const dbCount = (workload?.database_types || []).length;
  const hwAge = Number(workload?.hardware_age_years) || 0;
  const complianceCount = (req?.compliance?.regulatory_frameworks || []).length;
  const availability = Number(req?.performance?.availability_target) || 99.9;

  if (servers > 20) { score += 2; reasons.push(`${servers} servers to migrate`); }
  else if (servers > 5) { score += 1; }

  if (dataTb > 50) { score += 2; reasons.push(`${dataTb} TB of data`); }
  else if (dataTb > 10) { score += 1; }

  if (dbCount > 3) { score += 2; reasons.push(`${dbCount} database types`); }
  else if (dbCount > 1) { score += 1; }

  if (hwAge > 7) { score += 1; reasons.push('Aging hardware'); }

  if (complianceCount > 2) { score += 2; reasons.push(`${complianceCount} compliance frameworks`); }
  else if (complianceCount > 0) { score += 1; }

  if (availability >= 99.99) { score += 2; reasons.push('99.99%+ uptime requirement'); }
  else if (availability >= 99.9) { score += 1; }

  if (score <= 2) return { level: 'Low', timeline: '1–2 weeks', color: 'success', reasons };
  if (score <= 5) return { level: 'Medium', timeline: '1–3 months', color: 'warning', reasons };
  return { level: 'High', timeline: '2–6 months', color: 'error', reasons };
}

// ── Provider metadata ───────────────────────────────────────────────────────

const PROVIDER_META: Record<string, { icon: string; strengths: string[]; bestFor: string[] }> = {
  AWS: {
    icon: '☁️',
    strengths: [
      'Largest service catalog (200+ services)',
      'Best-in-class migration tooling (AWS MGN, DMS)',
      'Widest global region coverage',
      'Mature ecosystem & partner network',
    ],
    bestFor: ['General workloads', 'E-commerce', 'Startups to Enterprise', 'Serverless'],
  },
  Azure: {
    icon: '🔷',
    strengths: [
      'Deep Microsoft/Windows integration',
      'Strong compliance & government certifications',
      'Azure Arc for hybrid cloud',
      'Best enterprise identity (Azure AD)',
    ],
    bestFor: ['Microsoft shops', 'Government', 'Finance & Healthcare', 'Hybrid cloud'],
  },
  GCP: {
    icon: '🌐',
    strengths: [
      'Leading AI/ML platform (Vertex AI)',
      'Best Kubernetes (GKE)',
      'Competitive pricing with sustained-use discounts',
      'Superior data analytics (BigQuery)',
    ],
    bestFor: ['AI/ML workloads', 'Data analytics', 'Containers', 'Cost-sensitive projects'],
  },
};

// ── Results step ────────────────────────────────────────────────────────────

const ResultsStep: React.FC<{ org: any; workload: any; req: any }> = ({ org, workload, req }) => {
  const scores = scoreProviders(org, workload, req);
  const sorted = Object.entries(scores).sort(([, a], [, b]) => b - a);
  const [topProvider, topScore] = sorted[0];
  const maxScore = topScore;
  const complexity = getMigrationComplexity(workload, req);
  const targetCost = req?.budget?.target_monthly_cost || 4000;

  const costMultipliers: Record<string, number> = { AWS: 1.0, Azure: 0.95, GCP: 0.90 };

  return (
    <Box>
      <Alert severity="success" sx={{ mb: 3 }}>
        Assessment complete. Here's your personalised cloud recommendation.
      </Alert>

      {/* Top recommendation */}
      <Paper sx={{ p: 3, mb: 3, border: '2px solid', borderColor: 'success.main', bgcolor: 'success.light' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h3" sx={{ mr: 2 }}>{PROVIDER_META[topProvider]?.icon}</Typography>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h5" sx={{ fontWeight: 'bold', color: 'success.dark' }}>
                {topProvider}
              </Typography>
              <Chip label="Recommended" color="success" size="small" icon={<CheckCircleIcon />} />
            </Box>
            <Typography variant="body2" color="success.dark">
              Score: {topScore} points — best match for your requirements
            </Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>Key Strengths</Typography>
            {PROVIDER_META[topProvider]?.strengths.map((s, i) => (
              <Typography key={i} variant="body2" sx={{ ml: 1, mb: 0.5 }}>• {s}</Typography>
            ))}
          </Grid>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>Best For</Typography>
            {PROVIDER_META[topProvider]?.bestFor.map((s, i) => (
              <Typography key={i} variant="body2" sx={{ ml: 1, mb: 0.5 }}>• {s}</Typography>
            ))}
          </Grid>
          <Grid item xs={12}>
            <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                Estimated Monthly Cost: ${Math.round(targetCost * (costMultipliers[topProvider] || 1)).toLocaleString()}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Based on your target budget of ${targetCost.toLocaleString()}/month
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Migration complexity */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Migration Complexity</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Chip
            label={complexity.level}
            color={complexity.color}
            icon={complexity.level === 'Low' ? <CheckCircleIcon /> : <WarningAmberIcon />}
            sx={{ fontWeight: 'bold', fontSize: '1rem', px: 1 }}
          />
          <Typography variant="body1">
            Estimated timeline: <strong>{complexity.timeline}</strong>
          </Typography>
        </Box>
        {complexity.reasons.length > 0 && (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Complexity factors:</Typography>
            {complexity.reasons.map((r, i) => (
              <Typography key={i} variant="body2" sx={{ ml: 1 }}>• {r}</Typography>
            ))}
          </Box>
        )}
      </Paper>

      {/* Score comparison */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Provider Score Comparison</Typography>
        {sorted.map(([provider, score], idx) => (
          <Box key={provider} sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography>{PROVIDER_META[provider]?.icon}</Typography>
                <Typography variant="body2" sx={{ fontWeight: idx === 0 ? 'bold' : 'normal' }}>
                  {provider}
                </Typography>
                {idx === 0 && <Chip label="Top Pick" size="small" color="success" />}
              </Box>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>{score} pts</Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={(score / maxScore) * 100}
              color={idx === 0 ? 'success' : 'primary'}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        ))}
      </Paper>

      {/* Alternatives */}
      <Typography variant="h6" gutterBottom>Alternative Options</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {sorted.slice(1).map(([provider, score]) => {
          const meta = PROVIDER_META[provider];
          return (
            <Grid item xs={12} md={6} key={provider}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h4" sx={{ mr: 1 }}>{meta?.icon}</Typography>
                    <Box>
                      <Typography variant="h6" sx={{ fontWeight: 'bold' }}>{provider}</Typography>
                      <Typography variant="body2" color="text.secondary">Score: {score} pts</Typography>
                    </Box>
                  </Box>
                  {meta?.strengths.slice(0, 3).map((s, i) => (
                    <Typography key={i} variant="body2" sx={{ ml: 1, mb: 0.5 }}>• {s}</Typography>
                  ))}
                  <Box sx={{ mt: 2, p: 1.5, bgcolor: 'grey.100', borderRadius: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      Est. Monthly: ${Math.round(targetCost * (costMultipliers[provider] || 1)).toLocaleString()}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {/* Summary */}
      <Typography variant="h6" gutterBottom>Your Assessment Summary</Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>Organization</Typography>
            <Typography variant="body2" color="text.secondary">Size: {org?.company_size}</Typography>
            <Typography variant="body2" color="text.secondary">Industry: {org?.industry}</Typography>
            <Typography variant="body2" color="text.secondary">IT Team: {org?.it_team_size} people</Typography>
            <Typography variant="body2" color="text.secondary">Cloud XP: {org?.cloud_experience_level}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>Infrastructure</Typography>
            <Typography variant="body2" color="text.secondary">Servers: {workload?.physical_servers}</Typography>
            <Typography variant="body2" color="text.secondary">CPU Cores: {workload?.total_compute_cores}</Typography>
            <Typography variant="body2" color="text.secondary">Memory: {workload?.total_memory_gb} GB</Typography>
            <Typography variant="body2" color="text.secondary">Data: {workload?.data_volume_tb} TB</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>Requirements</Typography>
            <Typography variant="body2" color="text.secondary">Uptime: {req?.performance?.availability_target}%</Typography>
            <Typography variant="body2" color="text.secondary">Budget: ${req?.budget?.migration_budget?.toLocaleString()}</Typography>
            <Typography variant="body2" color="text.secondary">Cost Priority: {req?.budget?.cost_optimization_priority}</Typography>
            <Typography variant="body2" color="text.secondary">Compliance: {req?.compliance?.regulatory_frameworks?.length || 0} frameworks</Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

// ── Main wizard ─────────────────────────────────────────────────────────────

const MigrationWizard: React.FC = () => {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);

  const loadSaved = () => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch { /* ignore */ }
    return null;
  };
  const saved = loadSaved();
  const [orgData, setOrgData] = useState<any>(saved?.org || defaultOrgData);
  const [workloadData, setWorkloadData] = useState<any>(saved?.workload || defaultWorkloadData);
  const [reqData, setReqData] = useState<any>(saved?.req || defaultRequirementsData);

  // Auto-save to sessionStorage
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ org: orgData, workload: workloadData, req: reqData }));
  }, [orgData, workloadData, reqData]);

  const handleOrgChange = useCallback((data: any) => setOrgData(data), []);
  const handleWorkloadChange = useCallback((data: any) => setWorkloadData(data), []);
  const handleReqChange = useCallback((data: any) => setReqData(data), []);

  const handleNext = () => setActiveStep((s) => Math.min(s + 1, steps.length - 1));
  const handleBack = () => setActiveStep((s) => Math.max(s - 1, 0));

  const handleReset = () => {
    sessionStorage.removeItem(STORAGE_KEY);
    setOrgData(defaultOrgData);
    setWorkloadData(defaultWorkloadData);
    setReqData(defaultRequirementsData);
    setActiveStep(0);
  };

  const progress = Math.round((activeStep / (steps.length - 1)) * 100);

  const stepContent = [
    <OrganizationProfileForm key="org" data={orgData} onChange={handleOrgChange} />,
    <WorkloadProfileForm key="workload" data={workloadData} onChange={handleWorkloadChange} />,
    <RequirementsForm key="req" data={reqData} onChange={handleReqChange} />,
    <ResultsStep key="results" org={orgData} workload={workloadData} req={reqData} />,
  ];

  return (
    <Container maxWidth="lg">
      {/* Module nav bar */}
      <AppBar
        position="static"
        elevation={0}
        sx={{
          bgcolor: 'transparent',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          mb: 2,
          mt: -1,
        }}
      >
        <Toolbar disableGutters sx={{ minHeight: '48px !important' }}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/select')}
            sx={{ color: 'text.secondary', '&:hover': { color: 'white' }, mr: 2 }}
            size="small"
          >
            All Services
          </Button>
          <Typography variant="body2" color="text.secondary">
            / Cloud Migration Planner
          </Typography>
        </Toolbar>
      </AppBar>

      <Box sx={{ mt: 2, mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Cloud Migration Planner
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Answer a few questions and we'll recommend the best cloud platform for your migration — AWS, Azure, or GCP.
        </Typography>

        <Paper sx={{ p: 3, mt: 3 }}>
          <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>

          <Box sx={{ minHeight: 400 }}>
            {stepContent[activeStep]}
          </Box>

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
            <Button disabled={activeStep === 0} onClick={handleBack}>
              Back
            </Button>
            <Box sx={{ display: 'flex', gap: 1 }}>
              {activeStep === steps.length - 1 ? (
                <Button variant="outlined" onClick={handleReset}>
                  Start Over
                </Button>
              ) : (
                <Button variant="contained" onClick={handleNext}>
                  {activeStep === steps.length - 2 ? 'Get Recommendation' : 'Next'}
                </Button>
              )}
            </Box>
          </Box>
        </Paper>

        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="body2" gutterBottom>Progress: {progress}%</Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 4 }} />
        </Paper>
      </Box>
    </Container>
  );
};

export default MigrationWizard;
