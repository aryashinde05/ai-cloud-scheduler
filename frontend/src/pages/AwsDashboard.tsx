import React, { useState, useEffect } from 'react';
import { Grid, Card, CardContent, Typography, Box, LinearProgress, Alert, Chip, Button, IconButton, Tooltip } from '@mui/material';
import { motion } from 'framer-motion';
import {
  TrendingUp, AttachMoney, Savings, Warning,
  AccountBalance, CloudOff, Refresh, Info,
} from '@mui/icons-material';
import {
  XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip,
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area, Legend,
} from 'recharts';
import toast from 'react-hot-toast';
import apiService from '../services/api';
import numeral from 'numeral';
import { useNavigate } from 'react-router-dom';
import { SkeletonLoader } from '../components/Loading';
import { usePrefetch } from '../hooks/usePrefetch';
import { performanceMonitor } from '../utils/performanceMonitor';
import {
  AXIS_STYLE, GRID_STYLE, formatCurrencyCompact,
  CurrencyTooltip, PieChartCurrencyTooltip, LEGEND_CONFIG,
  CustomPieLabel, HOVER_CONFIG,
} from '../utils/chartConfig';

const StatCard: React.FC<{
  title: string; value: string; change: string; icon: React.ReactNode; color: string;
}> = React.memo(({ title, value, change, icon, color }) => (
  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>{title}</Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{value}</Typography>
            <Typography variant="body2" sx={{ color }}>{change}</Typography>
          </Box>
          <Box sx={{ color, opacity: 0.8 }}>{icon}</Box>
        </Box>
      </CardContent>
    </Card>
  </motion.div>
));

const AwsDashboard: React.FC = () => {
  const [finopsData, setFinopsData] = useState<any>(null);
  const [costTrendData, setCostTrendData] = useState<any[]>([]);
  const [serviceBreakdown, setServiceBreakdown] = useState<any[]>([]);
  const [budgetData, setBudgetData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const navigate = useNavigate();

  usePrefetch();

  useEffect(() => {
    performanceMonitor.start('AwsDashboard-Load');
    loadData();
  }, []);

  const loadData = async () => {
    const isRefresh = !loading;
    isRefresh ? setRefreshing(true) : setLoading(true);

    try {
      const [costsResponse, budgets, recommendations] = await Promise.all([
        apiService.getCosts({
          startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          endDate: new Date().toISOString().split('T')[0],
          granularity: 'DAILY',
        }).catch(() => ({ data: [], total: 0 })),
        apiService.getBudgets().catch(() => [] as any[]),
        apiService.getOptimizationRecommendations().catch(() => [] as any[]),
      ]);

      const costData: any[] = Array.isArray((costsResponse as any)?.data) ? (costsResponse as any).data : [];
      const recsArray: any[] = Array.isArray(recommendations) ? recommendations as any[] : [];
      const budgetsArray: any[] = Array.isArray(budgets) ? budgets as any[] : [];

      const totalCost = costData.reduce((s: number, i: any) => s + (i?.cost || 0), 0);
      const totalSavings = recsArray.reduce((s: number, i: any) => s + (i?.monthlySavings || 0), 0);
      const avgUtil = budgetsArray.length > 0
        ? budgetsArray.reduce((s: number, b: any) => s + (b?.utilization || 0), 0) / budgetsArray.length
        : 0;

      const dateMap = new Map<string, number>();
      costData.forEach((i: any) => dateMap.set(i.date, (dateMap.get(i.date) || 0) + (i.cost || 0)));
      const chartData = Array.from(dateMap.entries())
        .map(([date, amount]) => ({ date, amount }))
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

      setFinopsData({ monthlyCost: totalCost, savingsPotential: totalSavings, budgetUtilization: avgUtil });
      setCostTrendData(chartData);
      setServiceBreakdown([]);
      setBudgetData(budgetsArray.map((b: any) => ({ name: b.name, budget: b.amount, spent: b.spent, utilization: b.utilization })));
      setLastRefresh(new Date());
      if (isRefresh) toast.success('Dashboard refreshed');
    } catch {
      toast.error('Failed to load AWS data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
      performanceMonitor.end('AwsDashboard-Load');
    }
  };

  if (loading) return <SkeletonLoader variant="dashboard" />;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 4 }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Button size="small" variant="text" onClick={() => navigate('/dashboard')} sx={{ color: 'text.secondary', p: 0, minWidth: 0 }}>
              ← Dashboard
            </Button>
          </Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>AWS Dashboard</Typography>
          <Chip
            icon={<AccountBalance sx={{ fontSize: '14px !important' }} />}
            label="Amazon Web Services"
            size="small"
            sx={{ mt: 1, bgcolor: 'rgba(255,152,0,0.1)', color: '#ff9800', border: '1px solid rgba(255,152,0,0.3)' }}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" onClick={() => navigate('/onboarding')}
            sx={{ borderColor: '#ff9800', color: '#ff9800' }}>
            Manage Connection
          </Button>
          <Tooltip title="Refresh">
            <IconButton onClick={loadData} disabled={refreshing}
              sx={{ bgcolor: 'rgba(255,152,0,0.1)', '&:hover': { bgcolor: 'rgba(255,152,0,0.2)' } }}>
              <Refresh sx={{ animation: refreshing ? 'spin 1s linear infinite' : 'none',
                '@keyframes spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } } }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Alert severity={finopsData?.budgetUtilization > 95 ? 'error' : finopsData?.budgetUtilization > 85 ? 'warning' : 'success'} sx={{ mb: 4 }}>
        Budget: {finopsData?.budgetUtilization > 95 ? 'Critical — exceeded' : finopsData?.budgetUtilization > 85 ? 'Warning — approaching limit' : 'On track'}
        {` (${Math.round(finopsData?.budgetUtilization || 0)}% utilized)`}
      </Alert>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        {[
          { title: 'Monthly Cost', value: numeral(finopsData?.monthlyCost).format('$0,0'), change: 'last 30 days', icon: <AttachMoney sx={{ fontSize: 40 }} />, color: '#ff9800' },
          { title: 'Potential Savings', value: numeral(finopsData?.savingsPotential).format('$0,0'), change: 'identified', icon: <Savings sx={{ fontSize: 40 }} />, color: '#4caf50' },
          { title: 'Budget Utilization', value: `${Math.round(finopsData?.budgetUtilization || 0)}%`, change: 'of total budget', icon: <Warning sx={{ fontSize: 40 }} />, color: finopsData?.budgetUtilization > 85 ? '#f44336' : '#4caf50' },
          { title: 'Cost Trend', value: costTrendData.length > 0 ? 'Active' : 'No data', change: 'last 30 days', icon: <TrendingUp sx={{ fontSize: 40 }} />, color: '#2196f3' },
        ].map((card, i) => (
          <Grid item xs={12} sm={6} md={3} key={i}>
            <StatCard {...card} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>Cost Trend (Last 30 Days)</Typography>
              {costTrendData.length > 0 ? (
                <ResponsiveContainer width="100%" height={320}>
                  <AreaChart data={costTrendData}>
                    <CartesianGrid {...GRID_STYLE} />
                    <XAxis dataKey="date" {...AXIS_STYLE} />
                    <YAxis {...AXIS_STYLE} tickFormatter={formatCurrencyCompact} />
                    <ChartTooltip content={<CurrencyTooltip />} />
                    <Legend {...LEGEND_CONFIG} />
                    <Area type="monotone" dataKey="amount" name="Daily Cost" stroke="#ff9800" fill="rgba(255,152,0,0.15)" strokeWidth={3} {...HOVER_CONFIG} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <Info sx={{ fontSize: 48, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
                  <Typography color="text.secondary">No cost data yet. AWS Cost Explorer data appears within 24h of first usage.</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>Cost by Service</Typography>
              {serviceBreakdown.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={serviceBreakdown} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value" label={CustomPieLabel}>
                      {serviceBreakdown.map((_, i) => <Cell key={i} fill={['#ff9800','#2196f3','#4caf50','#f44336','#9c27b0'][i % 5]} />)}
                    </Pie>
                    <ChartTooltip content={<PieChartCurrencyTooltip />} />
                    <Legend {...LEGEND_CONFIG} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <Info sx={{ fontSize: 48, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
                  <Typography color="text.secondary" variant="body2">Service breakdown appears after AWS Cost Explorer processes your data.</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {budgetData.length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 3 }}>Budget Utilization</Typography>
                <Grid container spacing={3}>
                  {budgetData.map((b) => (
                    <Grid item xs={12} md={3} key={b.name}>
                      <Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" fontWeight={600}>{b.name}</Typography>
                          <Chip label={`${b.utilization}%`} size="small" sx={{
                            bgcolor: b.utilization > 90 ? 'rgba(244,67,54,0.2)' : b.utilization > 75 ? 'rgba(255,152,0,0.2)' : 'rgba(76,175,80,0.2)',
                            color: b.utilization > 90 ? '#f44336' : b.utilization > 75 ? '#ff9800' : '#4caf50',
                          }} />
                        </Box>
                        <LinearProgress variant="determinate" value={b.utilization} sx={{
                          height: 8, borderRadius: 4, bgcolor: 'rgba(255,255,255,0.1)',
                          '& .MuiLinearProgress-bar': { bgcolor: b.utilization > 90 ? '#f44336' : b.utilization > 75 ? '#ff9800' : '#4caf50' },
                        }} />
                        <Typography variant="caption" color="text.secondary">
                          {numeral(b.spent).format('$0,0')} / {numeral(b.budget).format('$0,0')}
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};

export default AwsDashboard;
