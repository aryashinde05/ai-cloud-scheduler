import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Chip,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  LinearProgress,
  Tabs,
  Tab,
} from '@mui/material';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  PlayArrow,
  Pause,
  CheckCircle,
  Warning,
  Info,
  Schedule,
  Savings,
  Memory,
  Storage,
  CloudOff,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import numeral from 'numeral';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { SkeletonLoader } from '../components/Loading';
import { api } from '../services/api';
import {
  TOOLTIP_STYLE,
  AXIS_STYLE,
  GRID_STYLE,
  formatCurrency,
  PieChartCurrencyTooltip,
  LEGEND_CONFIG,
  CustomPieLabel,
} from '../utils/chartConfig';

const Optimization: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState(0);
  const [implementDialogOpen, setImplementDialogOpen] = useState(false);
  const [selectedRecommendation, setSelectedRecommendation] = useState<any>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [implementing, setImplementing] = useState(false);
  const [autoModeEnabled, setAutoModeEnabled] = useState<boolean>(false);
  const [autoModeLoading, setAutoModeLoading] = useState<boolean>(true);
  const [loading, setLoading] = useState(true);
  const [noAws, setNoAws] = useState(false);
  const [optimizationOpportunities, setOptimizationOpportunities] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadAutoMode();
    loadOptimizationData();
  }, []);

  const loadAutoMode = async () => {
    try {
      setAutoModeLoading(true);
      const res = await api.get('/optimize/auto-mode');
      setAutoModeEnabled(!!res.data?.enabled);
    } catch (e) {
      console.error('Error loading auto mode:', e);
    } finally {
      setAutoModeLoading(false);
    }
  };

  const toggleAutoMode = async (enabled: boolean) => {
    try {
      setAutoModeLoading(true);
      const res = await api.put('/optimize/auto-mode', { enabled });
      setAutoModeEnabled(!!res.data?.enabled);
      toast.success(res.data?.enabled ? 'Auto mode enabled' : 'Auto mode disabled');
    } catch (e) {
      console.error('Error updating auto mode:', e);
      const msg =
        (e as any)?.response?.data?.error?.message ||
        (e as any)?.response?.data?.detail ||
        (e as any)?.message ||
        'Failed to update auto mode';
      toast.error(msg);
    } finally {
      setAutoModeLoading(false);
    }
  };

  const loadOptimizationData = async () => {
    try {
      setLoading(true);

      // Check AWS connection first
      const statusRes = await api.get('/api/v1/aws/status');
      if (!statusRes.data?.connected) {
        setNoAws(true);
        setLoading(false);
        return;
      }

      const [actionsRes, statsRes] = await Promise.all([
        api.get('/api/v1/automation/actions'),
        api.get('/api/v1/automation/reports/summary').catch(() => ({ data: null })),
      ]);

      const actionsData = actionsRes.data;
      const statsData = statsRes.data;

      // Transform action data into optimization opportunities format
      const opportunities = (Array.isArray(actionsData) ? actionsData : []).map((action: any, i: number) => ({
        id: i + 1,
        type: action.action_type === 'resize_underutilized_instances' ? 'rightsizing' :
          action.action_type === 'terminate_instance' ? 'termination' :
            action.action_type === 'delete_volumes' ? 'termination' :
              action.action_type === 'release_elastic_ips' ? 'termination' :
                'rightsizing',
        resource: action.action_id || 'unknown',
        resourceType: action.resource_type === 'ec2_instance' ? 'EC2 Instance' :
          action.resource_type === 'ebs_volume' ? 'EBS Volume' :
            action.resource_type === 'elastic_ip' ? 'Elastic IP' :
              action.resource_type || 'Resource',
        currentConfig: action.current_config || action.name || '',
        recommendedConfig: action.recommended_config || action.description || '',
        monthlySavings: action.potential_savings || 0,
        annualSavings: (action.potential_savings || 0) * 12,
        confidence: action.confidence || 85,
        riskLevel: action.risk_level || 'low',
        status: action.status === 'enabled' ? 'new' : action.status || 'new',
        team: 'Infrastructure',
        utilization: { cpu: 0, memory: 0 },
      }));

      setOptimizationOpportunities(opportunities);
      setStats(statsData);
      setLoading(false);
    } catch (error) {
      console.error('Error loading optimization data:', error);
      setLoading(false);
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'rightsizing':
        return <Memory sx={{ fontSize: 16 }} />;
      case 'termination':
        return <TrendingDown sx={{ fontSize: 16 }} />;
      case 'ri_purchase':
        return <Savings sx={{ fontSize: 16 }} />;
      case 'storage_class':
        return <Storage sx={{ fontSize: 16 }} />;
      default:
        return <TrendingUp sx={{ fontSize: 16 }} />;
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'rightsizing': return '#ff9800';
      case 'termination': return '#f44336';
      case 'ri_purchase': return '#4caf50';
      case 'storage_class': return '#2196f3';
      default: return '#9e9e9e';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'new': return '#2196f3';
      case 'in_progress': return '#ff9800';
      case 'implemented': return '#4caf50';
      case 'dismissed': return '#9e9e9e';
      default: return '#9e9e9e';
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'none': return '#4caf50';
      case 'low': return '#8bc34a';
      case 'medium': return '#ff9800';
      case 'high': return '#f44336';
      default: return '#9e9e9e';
    }
  };

  const handleImplement = (recommendation: any) => {
    setSelectedRecommendation(recommendation);
    setConfirmDelete(false);
    setImplementDialogOpen(true);
  };

  const mapResourceType = (rec: any): 'ec2_instance' | 'ebs_volume' | null => {
    const rt = (rec?.resourceType || '').toLowerCase();
    if (rt.includes('ec2')) return 'ec2_instance';
    if (rt.includes('ebs')) return 'ebs_volume';
    return null;
  };

  const confirmImplementation = async () => {
    if (selectedRecommendation) {
      try {
        const resourceType = mapResourceType(selectedRecommendation);
        if (!resourceType) {
          toast.error('Unsupported resource type for execution');
          return;
        }

        setImplementing(true);
        const res = await api.post(`/optimize/execute`, {
          resource_id: selectedRecommendation.resource,
          resource_type: resourceType,
          confirm_delete: resourceType === 'ebs_volume' ? confirmDelete : false,
        });

        if (res.data?.status === 'success') {
          const actions: string[] = Array.isArray(res.data?.actions) ? res.data.actions : [];
          if (actions.includes('stopped EC2')) {
            toast.success('Instance stopped successfully');
          } else if (actions.includes('deleted volume')) {
            toast.success('Volume deleted successfully');
          } else if (actions.includes('skipped EC2 (DoNotStop=true)')) {
            toast.success('Instance skipped (DoNotStop tag)');
          } else {
            toast.success('Action executed successfully');
          }
          await loadOptimizationData();
        } else {
          toast.error('Failed to execute optimization action');
        }
      } catch (e) {
        console.error('Error executing action:', e);
        const msg =
          (e as any)?.response?.data?.error?.message ||
          (e as any)?.response?.data?.detail ||
          (e as any)?.message ||
          'Error executing action';
        toast.error(msg);
      } finally {
        setImplementing(false);
      }
    }
    setImplementDialogOpen(false);
    setSelectedRecommendation(null);
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" sx={{ mb: 4, fontWeight: 700 }}>Cost Optimization</Typography>
        <SkeletonLoader variant="table" count={8} />
      </Box>
    );
  }

  if (noAws) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <CloudOff sx={{ fontSize: 80, color: 'text.secondary', mb: 3 }} />
        <Typography variant="h4" sx={{ mb: 2, fontWeight: 700 }}>No AWS Account Connected</Typography>
        <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
          Connect your AWS account to see optimization recommendations.
        </Typography>
        <Button variant="contained" size="large" onClick={() => navigate('/onboarding')}>
          Connect AWS Account
        </Button>
      </Box>
    );
  }

  const totalPotentialSavings = optimizationOpportunities.reduce((sum, opp) => sum + opp.annualSavings, 0);

  // Group by type for chart
  const optimizationTypes: { name: string; count: number; savings: number; color: string }[] = [];
  const typeMap: Record<string, { count: number; savings: number }> = {};
  const typeColors: Record<string, string> = { rightsizing: '#ff9800', termination: '#f44336', ri_purchase: '#4caf50', storage_class: '#2196f3' };

  optimizationOpportunities.forEach(opp => {
    if (!typeMap[opp.type]) typeMap[opp.type] = { count: 0, savings: 0 };
    typeMap[opp.type].count += 1;
    typeMap[opp.type].savings += opp.annualSavings;
  });
  Object.entries(typeMap).forEach(([type, data]) => {
    optimizationTypes.push({ name: type.replace('_', ' '), count: data.count, savings: data.savings, color: typeColors[type] || '#9e9e9e' });
  });

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>Cost Optimization</Typography>
        <FormControlLabel
          control={
            <Switch
              checked={autoModeEnabled}
              onChange={(e) => toggleAutoMode(e.target.checked)}
              disabled={autoModeLoading}
              color="success"
            />
          }
          label={autoModeEnabled ? 'Auto mode ON' : 'Auto mode OFF'}
        />
      </Box>

      {/* Optimization Overview Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Potential Savings</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{numeral(totalPotentialSavings).format('$0,0')}</Typography>
              <Chip label="Annual" size="small" sx={{ backgroundColor: 'rgba(76, 175, 80, 0.2)', color: '#4caf50' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Monthly Savings</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{numeral(stats?.monthly_savings || 0).format('$0,0')}</Typography>
              <Chip label="Per Month" size="small" sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Active Recommendations</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{optimizationOpportunities.filter(o => o.status === 'new').length}</Typography>
              <Chip label="Need review" size="small" sx={{ backgroundColor: 'rgba(255, 152, 0, 0.2)', color: '#ff9800' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Total Actions</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{stats?.total_actions || 0}</Typography>
              <Chip label="Identified" size="small" sx={{ backgroundColor: 'rgba(76, 175, 80, 0.2)', color: '#4caf50' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Optimization Types Breakdown */}
      {optimizationTypes.length > 0 && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} lg={4}>
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }}>
              <Card><CardContent>
                <Typography variant="h6" sx={{ mb: 3 }}>Optimization Types</Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie 
                      data={optimizationTypes} 
                      cx="50%" 
                      cy="50%" 
                      innerRadius={50} 
                      outerRadius={80} 
                      paddingAngle={5} 
                      dataKey="savings"
                      label={CustomPieLabel}
                    >
                      {optimizationTypes.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      content={({ active, payload }: any) => {
                        if (active && payload && payload.length) {
                          const data = payload[0];
                          return (
                            <div style={TOOLTIP_STYLE}>
                              <p style={{ margin: 0, marginBottom: 4, fontWeight: 600, color: '#fff', textTransform: 'capitalize' }}>
                                {data.payload.name}
                              </p>
                              <p style={{ margin: 0, color: data.payload.fill, fontSize: 14 }}>
                                <span style={{ fontWeight: 600 }}>Savings:</span> {formatCurrency(data.value)}
                              </p>
                              <p style={{ margin: 0, color: '#b0bec5', fontSize: 12 }}>
                                {data.payload.count} opportunities
                              </p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend {...LEGEND_CONFIG} formatter={(value, entry: any) => entry.payload.name} />
                  </PieChart>
                </ResponsiveContainer>
                <Box sx={{ mt: 2 }}>
                  {optimizationTypes.map((type) => (
                    <Box key={type.name} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <Box sx={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: type.color, mr: 1 }} />
                      <Typography variant="body2" sx={{ flexGrow: 1, fontSize: '0.8rem', textTransform: 'capitalize' }}>{type.name}</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{type.count}</Typography>
                    </Box>
                  ))}
                </Box>
              </CardContent></Card>
            </motion.div>
          </Grid>
        </Grid>
      )}

      {/* Recommendations Table */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6">Optimization Recommendations</Typography>
              </Box>
              {optimizationOpportunities.length > 0 ? (
                <TableContainer component={Paper} sx={{ backgroundColor: 'transparent' }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Resource</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Current Config</TableCell>
                        <TableCell>Recommended</TableCell>
                        <TableCell align="right">Monthly Savings</TableCell>
                        <TableCell align="center">Confidence</TableCell>
                        <TableCell align="center">Risk</TableCell>
                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {optimizationOpportunities.map((opportunity) => (
                        <TableRow key={opportunity.id}>
                          <TableCell component="th" scope="row">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{opportunity.resource}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>{opportunity.resourceType}</Typography>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <Box sx={{ color: getTypeColor(opportunity.type), mr: 1 }}>{getTypeIcon(opportunity.type)}</Box>
                              <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{opportunity.type.replace('_', ' ')}</Typography>
                            </Box>
                          </TableCell>
                          <TableCell><Typography variant="body2">{opportunity.currentConfig}</Typography></TableCell>
                          <TableCell><Typography variant="body2">{opportunity.recommendedConfig}</Typography></TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontWeight: 600, color: '#4caf50' }}>{numeral(opportunity.monthlySavings).format('$0,0')}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>{numeral(opportunity.annualSavings).format('$0,0')}/year</Typography>
                          </TableCell>
                          <TableCell align="center">
                            <LinearProgress variant="determinate" value={opportunity.confidence}
                              sx={{
                                width: 60, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.1)',
                                '& .MuiLinearProgress-bar': { backgroundColor: opportunity.confidence > 90 ? '#4caf50' : opportunity.confidence > 70 ? '#ff9800' : '#f44336' }
                              }} />
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>{opportunity.confidence}%</Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Chip label={opportunity.riskLevel} size="small"
                              sx={{ backgroundColor: `${getRiskColor(opportunity.riskLevel)}20`, color: getRiskColor(opportunity.riskLevel), textTransform: 'capitalize' }} />
                          </TableCell>
                          <TableCell align="center">
                            <Tooltip title="Implement Recommendation">
                              <IconButton size="small" onClick={() => handleImplement(opportunity)} sx={{ color: '#4caf50' }}>
                                <PlayArrow sx={{ fontSize: 16 }} />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="View Details">
                              <IconButton size="small"><Info sx={{ fontSize: 16 }} /></IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Alert severity="success" sx={{ mt: 2 }}>
                  No optimization recommendations found — your AWS resources are well-optimized!
                </Alert>
              )}
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Implementation Dialog */}
      <Dialog open={implementDialogOpen} onClose={() => setImplementDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Implement Optimization Recommendation</DialogTitle>
        <DialogContent>
          {selectedRecommendation && (
            <Box>
              {!autoModeEnabled && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  Auto mode is OFF. Turn it ON to allow real AWS execution. You can still review recommendations safely.
                </Alert>
              )}
              <Alert severity="info" sx={{ mb: 3 }}>
                You are about to implement an optimization that will save approximately{' '}
                <strong>{numeral(selectedRecommendation.monthlySavings).format('$0,0')}</strong> per month.
              </Alert>
              {mapResourceType(selectedRecommendation) === 'ebs_volume' && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  Deleting an EBS volume is permanent. Please confirm before continuing.
                </Alert>
              )}
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>Current Configuration:</Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>{selectedRecommendation.currentConfig}</Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>Recommended Configuration:</Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>{selectedRecommendation.recommendedConfig}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>Impact Analysis:</Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>• Monthly Savings: {numeral(selectedRecommendation.monthlySavings).format('$0,0')}</Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>• Annual Savings: {numeral(selectedRecommendation.annualSavings).format('$0,0')}</Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>• Confidence Level: {selectedRecommendation.confidence}%</Typography>
                  <Typography variant="body2">• Risk Level: {selectedRecommendation.riskLevel}</Typography>
                </Grid>
                {mapResourceType(selectedRecommendation) === 'ebs_volume' && (
                  <Grid item xs={12}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <input
                        id="confirm-delete"
                        type="checkbox"
                        checked={confirmDelete}
                        onChange={(e) => setConfirmDelete(e.target.checked)}
                        style={{ transform: 'scale(1.1)' }}
                      />
                      <label htmlFor="confirm-delete">
                        I understand this will permanently delete the EBS volume.
                      </label>
                    </Box>
                  </Grid>
                )}
              </Grid>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setImplementDialogOpen(false)} disabled={implementing}>Cancel</Button>
          <Button
            onClick={confirmImplementation}
            variant="contained"
            color="primary"
            disabled={
              implementing ||
              !autoModeEnabled ||
              (selectedRecommendation && mapResourceType(selectedRecommendation) === 'ebs_volume' && !confirmDelete)
            }
          >
            Implement Now
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Optimization;