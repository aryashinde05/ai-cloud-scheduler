import React, { useState } from 'react';
import { Box, Typography, Button, Paper, Grid, TextField, Card, CardContent, Divider, Chip, Stack, Alert } from '@mui/material';
import { useMutation } from 'react-query';
import { azureCostService } from '../services/azureCostService';
import { Analytics, Science, Insights, TrendingUp, AccountBalance } from '@mui/icons-material';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

export default function AzureAnalysis() {
  const [daysBack, setDaysBack] = useState(30);
  const navigate = useNavigate();
  
  const mutation = useMutation((data: { days_back: number }) => 
    azureCostService.analyzeCost(data)
  );

  const handleAnalyze = () => {
    mutation.mutate({ days_back: daysBack });
  };

  const report = mutation.data;

  return (
    <Box>
      <Helmet><title>Azure Cost Analysis | FinOps</title></Helmet>
      
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Deep Cost Analysis
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Run comprehensive analysis to identify trends and ROI of your Azure spend.
        </Typography>
      </Box>

      <Paper sx={{ p: 4, mb: 4, borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none' }}>
        <Grid container spacing={4} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="h6" mb={1}>Analysis Configuration</Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Select the time window for the analyzer to scan. Longer periods provide better trend insights.
            </Typography>
            <Stack direction="row" spacing={2}>
              <TextField
                type="number"
                label="Days to analyze"
                value={daysBack}
                onChange={(e) => setDaysBack(parseInt(e.target.value))}
                inputProps={{ min: 1, max: 365 }}
                sx={{ width: 150 }}
              />
              <Button 
                variant="contained" 
                size="large" 
                startIcon={<Science />}
                onClick={handleAnalyze}
                disabled={mutation.isLoading}
                sx={{ borderRadius: 2, px: 4 }}
              >
                {mutation.isLoading ? 'Analyzing...' : 'Run Analysis'}
              </Button>
            </Stack>
          </Grid>
          <Grid item xs={12} md={4} sx={{ display: 'flex', justifyContent: 'center' }}>
            <Analytics sx={{ fontSize: 120, color: 'primary.main', opacity: 0.2 }} />
          </Grid>
        </Grid>
      </Paper>

      {mutation.isError && (
        <Alert severity="error" sx={{ mb: 4, borderRadius: 2 }}>
          Analysis failed. Please ensure your subscription is active and has correct permissions.
        </Alert>
      )}

      {report && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={7}>
              <Card sx={{ height: '100%', borderRadius: 4 }}>
                <CardContent sx={{ p: 4 }}>
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Executive Summary
                  </Typography>
                  <Box sx={{ mt: 3, display: 'flex', gap: 4 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">Monthly Run Rate</Typography>
                      <Typography variant="h4" fontWeight={700}>${report.total_monthly_cost.toFixed(2)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">Cost Trend</Typography>
                      <Chip 
                        label={report.cost_trend.toUpperCase()} 
                        color={report.cost_trend === 'increasing' ? 'error' : 'success'} 
                        sx={{ mt: 0.5, fontWeight: 700 }} 
                      />
                    </Box>
                  </Box>

                  <Divider sx={{ my: 4, opacity: 0.1 }} />

                  <Typography variant="subtitle1" fontWeight={600} mb={2}>Key Findings</Typography>
                  <Stack spacing={2}>
                    {report.recommendations_summary.map((rec: string, i: number) => (
                      <Box key={i} sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                        <Insights color="primary" sx={{ mt: 0.5 }} />
                        <Typography variant="body2">{rec}</Typography>
                      </Box>
                    ))}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={5}>
              <Card sx={{ height: '100%', borderRadius: 4 }}>
                <CardContent sx={{ p: 4 }}>
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    ROI & Savings Potential
                  </Typography>
                  
                  <Box sx={{ mt: 4, textAlign: 'center' }}>
                    <AccountBalance sx={{ fontSize: 48, color: 'success.main', mb: 1, opacity: 0.8 }} />
                    <Typography variant="h3" fontWeight={800} color="success.main">
                      ${report.potential_monthly_savings.toFixed(2)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Potential Monthly Savings
                    </Typography>
                  </Box>

                  <Box sx={{ mt: 4, p: 3, borderRadius: 3, bgcolor: 'rgba(0, 200, 83, 0.05)', border: '1px solid rgba(0, 200, 83, 0.1)' }}>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">ANNUAL SAVINGS</Typography>
                        <Typography variant="h6">${report.roi_analysis.annual_savings.toFixed(2)}</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">EFFICIENCY GAIN</Typography>
                        <Typography variant="h6">${report.roi_analysis.roi_percentage.toFixed(1)}%</Typography>
                      </Grid>
                    </Grid>
                  </Box>

                  <Button 
                    fullWidth 
                    variant="contained" 
                    color="success" 
                    sx={{ mt: 4, borderRadius: 2, py: 1.5 }}
                    onClick={() => navigate('/azure/opportunities')}
                  >
                    Implement Recommendations
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </motion.div>
      )}

      {!report && !mutation.isLoading && (
        <Box sx={{ mt: 8, textAlign: 'center', opacity: 0.5 }}>
          <TrendingUp sx={{ fontSize: 48, mb: 1 }} />
          <Typography>Run an analysis to see detailed cost insights</Typography>
        </Box>
      )}
    </Box>
  );
}
