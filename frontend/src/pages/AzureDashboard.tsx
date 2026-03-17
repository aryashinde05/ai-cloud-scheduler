import React, { useEffect, useState } from 'react';
import { Box, Typography, Grid, Paper, List, ListItem, ListItemText, ListItemIcon, Button, Alert, Skeleton } from '@mui/material';
import { useQuery } from 'react-query';
import { useNavigate } from 'react-router-dom';
import { azureCostService } from '../services/azureCostService';
import { CostCard } from '../components/Azure/CostCard';
import { ChartCard } from '../components/Azure/ChartCard';
import { Loader } from '../components/Azure/Loader';
import { AttachMoney, ShowChart, CloudQueue, NotificationsActive, Link, TrendingUp, TrendingDown, TrendingFlat } from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';

const COLORS = ['#2196f3', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

export default function AzureDashboard() {
  const navigate = useNavigate();
  const [hasCredentials, setHasCredentials] = useState(false);

  useEffect(() => {
    const creds = localStorage.getItem('azure_credentials');
    setHasCredentials(!!creds);
  }, []);

  const { data: trendsData, isLoading: loadingTrends, error: trendsError } = useQuery(
    'azureCostTrends', 
    () => azureCostService.getCostTrends(30),
    { enabled: hasCredentials }
  );
  
  const { data: breakdownData, isLoading: loadingBreakdown } = useQuery(
    'azureServiceBreakdown', 
    () => azureCostService.getServiceBreakdown(30),
    { enabled: hasCredentials }
  );
  
  const { data: quickWins, isLoading: loadingQuickWins } = useQuery(
    'azureQuickWins', 
    azureCostService.getQuickWins,
    { enabled: hasCredentials }
  );

  if (!hasCredentials) {
    return (
       <Box textAlign="center" mt={10} p={4}>
         <Helmet><title>Azure Dashboard | FinOps</title></Helmet>
         <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
           <Typography variant="h4" fontWeight={700} gutterBottom>Azure Dashboard</Typography>
           <Paper sx={{ p: 6, mt: 4, maxWidth: 600, mx: 'auto', borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none' }}>
             <Typography variant="h6" mb={2}>No Azure Connection Found</Typography>
             <Typography color="text.secondary" mb={4}>
               Please connect your Azure account to view cost insights and recommendations.
             </Typography>
             <Button 
               variant="contained" 
               color="primary" 
               size="large"
               startIcon={<Link />}
               onClick={() => navigate('/azure/connection')}
               sx={{ borderRadius: 2 }}
             >
               Connect Azure Subscription
             </Button>
           </Paper>
         </motion.div>
       </Box>
    );
  }

  // Derive metrics
  const history = trendsData?.history || [];
  const totalCost = history.reduce((acc: number, item: any) => acc + (item.cost || 0), 0);
  const topService = breakdownData?.[0]?.service_name || 'N/A';
  const totalSavings = quickWins?.reduce((acc: number, item: any) => acc + (item.potential_monthly_savings || 0), 0) || 0;
  const trendDirection = trendsData?.direction || 'stable';

  const getTrendIcon = () => {
    if (trendDirection === 'increasing') return <TrendingUp sx={{ color: 'error.main', ml: 1 }} />;
    if (trendDirection === 'decreasing') return <TrendingDown sx={{ color: 'success.main', ml: 1 }} />;
    return <TrendingFlat sx={{ color: 'text.secondary', ml: 1 }} />;
  };

  return (
    <Box>
      <Helmet><title>Azure Dashboard | FinOps</title></Helmet>
      
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Azure Cost Control
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Cloud financial management and optimization for Azure.
          </Typography>
        </Box>
        <Button 
          variant="outlined" 
          onClick={() => navigate('/azure/analysis')}
          sx={{ borderRadius: 2 }}
        >
          View Detailed Analysis
        </Button>
      </Box>

      {!!trendsError && (
        <Alert severity="error" sx={{ mb: 4, borderRadius: 2 }}>
          Failed to load Azure data. Please check your credentials in the <Link href="#" onClick={(e) => { e.preventDefault(); navigate('/azure/connection'); }}>Connection</Link> page.
        </Alert>
      )}

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          {loadingTrends ? <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 4 }} /> : (
            <CostCard 
              title="Total 30-Day Cost" 
              value={`$${totalCost.toLocaleString(undefined, { minimumFractionDigits: 2 })}`} 
              icon={<AttachMoney />}
              subtitle={
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  Trend: {trendDirection.charAt(0).toUpperCase() + trendDirection.slice(1)}
                  {getTrendIcon()}
                </Box>
              }
            />
          )}
        </Grid>
        <Grid item xs={12} md={4}>
          {loadingQuickWins ? <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 4 }} /> : (
            <CostCard 
              title="Potential Savings" 
              value={`$${totalSavings.toLocaleString(undefined, { minimumFractionDigits: 2 })}`} 
              icon={<ShowChart />}
              subtitle={`From ${quickWins?.length || 0} optimization opportunities`}
            />
          )}
        </Grid>
        <Grid item xs={12} md={4}>
          {loadingBreakdown ? <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 4 }} /> : (
            <CostCard 
              title="Main Cost Driver" 
              value={topService} 
              icon={<CloudQueue />}
              subtitle={breakdownData?.length > 0 ? "Highest spend service" : "Analyzing services..."}
            />
          )}
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={8}>
          <ChartCard title="Daily Cost Trends (USD)">
            {loadingTrends ? <Skeleton variant="rectangular" height="100%" sx={{ borderRadius: 2 }} /> : history.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="#b0bec5" 
                    tick={{ fontSize: 12 }} 
                    tickFormatter={(str) => str.split('T')[0]} 
                  />
                  <YAxis stroke="#b0bec5" tick={{ fontSize: 12 }} />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: '#1a1d3a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="cost" 
                    stroke="#2196f3" 
                    strokeWidth={3} 
                    dot={false} 
                    activeDot={{ r: 6, strokeWidth: 0 }} 
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Box display="flex" alignItems="center" justifyContent="center" height="100%">
                <Typography color="text.secondary">No historical data available.</Typography>
              </Box>
            )}
          </ChartCard>
        </Grid>

        <Grid item xs={12} lg={4}>
          <ChartCard title="Cost by Service">
            {loadingBreakdown ? <Skeleton variant="rectangular" height="100%" sx={{ borderRadius: 2 }} /> : breakdownData?.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={breakdownData}
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="current_month_cost"
                    nameKey="service_name"
                  >
                    {breakdownData.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="none" />
                    ))}
                  </Pie>
                  <RechartsTooltip 
                     contentStyle={{ backgroundColor: '#1a1d3a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  />
                  <Legend verticalAlign="bottom" height={36}/>
                </PieChart>
              </ResponsiveContainer>
            ) : (
               <Box display="flex" alignItems="center" justifyContent="center" height="100%">
                 <Typography color="text.secondary">No breakdown available.</Typography>
               </Box>
            )}
          </ChartCard>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3, borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h6" fontWeight={600}>
                Top Optimization Opportunities
              </Typography>
              <Button color="primary" onClick={() => navigate('/azure/opportunities')}>
                View All Opportunities
              </Button>
            </Box>
            {loadingQuickWins ? (
              <Box sx={{ width: '100%' }}>
                <Skeleton height={60} />
                <Skeleton height={60} />
                <Skeleton height={60} />
              </Box>
            ) : quickWins?.length > 0 ? (
              <List disablePadding>
                {quickWins.slice(0, 5).map((win: any, i: number) => (
                  <ListItem 
                    key={i} 
                    sx={{ 
                      px: 0, 
                      py: 2, 
                      borderBottom: '1px solid rgba(255,255,255,0.05)', 
                      '&:last-child': { borderBottom: 'none' } 
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 48 }}>
                      <Box sx={{ 
                        p: 1, borderRadius: 1.5, bgcolor: 'rgba(33, 150, 243, 0.1)', color: 'primary.main' 
                      }}>
                        <NotificationsActive />
                      </Box>
                    </ListItemIcon>
                    <ListItemText 
                      primary={win.description}
                      secondary={
                        <Box component="span" sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
                          <Typography variant="body2" component="span" color="text.secondary">
                            Service: {win.service}
                          </Typography>
                          <Typography variant="body2" component="span" sx={{ color: 'success.main', fontWeight: 600 }}>
                            Potential Savings: ${win.potential_monthly_savings.toFixed(2)}/mo
                          </Typography>
                        </Box>
                      }
                      primaryTypographyProps={{ fontWeight: 600, fontSize: '1rem' }}
                    />
                    <Button variant="outlined" size="small" sx={{ borderRadius: 2 }}>
                      View Details
                    </Button>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography color="text.secondary">No immediate optimization opportunities found.</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
