import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Alert,
  Chip,
  Button,
  LinearProgress,
  Tabs,
  Tab,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
} from '@mui/material';
import {
  Warning as WarningIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
  Info as InfoIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { format, parseISO, subDays } from 'date-fns';

// Import new services and components
import { 
  anomalyApiService, 
  Anomaly, 
  ForecastResponse, 
  SystemStatus,
  AnomalyConfiguration 
} from '../services/anomalyApi';
import AnomalyConfigurationComponent from '../components/AnomalyConfiguration';
import ForecastVisualization from '../components/ForecastVisualization';
import ExplanationViewer from '../components/ExplanationViewer';

const AnomalyDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedAnomalyId, setSelectedAnomalyId] = useState<string | null>(null);
  const [explanationOpen, setExplanationOpen] = useState(false);
  const [configurationOpen, setConfigurationOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [accountId, setAccountId] = useState<string>('aws-account-123');

  useEffect(() => {
    // Initial load will wait for account ID to be fetched
    fetchAccountStatus();
  }, []);

  const fetchAccountStatus = async () => {
    setLoading(true);
    try {
      const { api } = await import('../services/api');
      const statusRes = await api.get('/api/v1/aws/status');
      if (statusRes.data?.connected && statusRes.data?.account_id) {
        setAccountId(statusRes.data.account_id);
      }
    } catch (e) {
      console.error("Failed to fetch AWS status, falling back to default account ID");
    } finally {
      // Once account is determined, load the dashboard data
      loadDashboardData();
    }
  };

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadAnomalies(),
        loadSystemStatus()
      ]);
    } catch (error: any) {
      console.error('Error loading dashboard data:', error);
      setError('Failed to load dashboard data: ' + (error.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const loadAnomalies = async () => {
    try {
      const endDate = new Date();
      const startDate = subDays(endDate, 7);
      
      const response = await anomalyApiService.getAnomalies({
        account_id: accountId,
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        limit: 50
      });

      setAnomalies(response.anomalies);
    } catch (error: any) {
      console.error('Error loading anomalies:', error);
      throw error;
    }
  };

  const loadSystemStatus = async () => {
    try {
      const status = await anomalyApiService.getSystemStatus();
      setSystemStatus(status);
    } catch (error: any) {
      console.error('Error loading system status:', error);
      throw error;
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const openAnomalyDetails = (anomalyId: string) => {
    setSelectedAnomalyId(anomalyId);
    setExplanationOpen(true);
  };

  const handleForecastGenerated = (newForecast: ForecastResponse) => {
    setForecast(newForecast);
  };

  const handleConfigurationChange = (config: AnomalyConfiguration) => {
    // Optionally reload data after configuration change
    loadAnomalies();
  };

  const getRiskColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'high': return 'error';
      case 'medium': return 'warning';
      case 'low': return 'success';
      default: return 'info';
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'error';
  };

  // Prepare chart data
  const prepareAnomalyServiceData = () => {
    const serviceCount: { [key: string]: number } = {};
    const serviceImpact: { [key: string]: number } = {};
    
    anomalies.forEach(anomaly => {
      anomaly.affected_services.forEach(service => {
        serviceCount[service] = (serviceCount[service] || 0) + 1;
        serviceImpact[service] = (serviceImpact[service] || 0) + anomaly.estimated_impact_usd;
      });
    });

    return Object.entries(serviceCount).map(([service, count]) => ({
      service,
      count,
      impact: serviceImpact[service] || 0,
      color: `hsl(${Math.random() * 360}, 70%, 50%)`
    }));
  };

  const prepareAnomalyTrendData = () => {
    const dailyAnomalies: { [key: string]: number } = {};
    
    anomalies.forEach(anomaly => {
      const date = format(parseISO(anomaly.detection_timestamp), 'MMM dd');
      dailyAnomalies[date] = (dailyAnomalies[date] || 0) + 1;
    });

    return Object.entries(dailyAnomalies).map(([date, count]) => ({
      date,
      count
    }));
  };

  // Calculate summary statistics
  const totalImpact = anomalies.reduce((sum, a) => sum + a.estimated_impact_usd, 0);
  const highSeverityCount = anomalies.filter(a => a.severity === 'high').length;
  const mediumSeverityCount = anomalies.filter(a => a.severity === 'medium').length;
  const lowSeverityCount = anomalies.filter(a => a.severity === 'low').length;
  const avgConfidence = anomalies.length > 0 ? 
    anomalies.reduce((sum, a) => sum + a.confidence_score, 0) / anomalies.length : 0;

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          AI Cost Anomaly Detection
        </Typography>
        <Box>
          <Tooltip title="Refresh Data">
            <IconButton onClick={loadDashboardData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Configuration">
            <IconButton onClick={() => setConfigurationOpen(true)}>
              <SettingsIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <WarningIcon color="warning" sx={{ mr: 1 }} />
                <Typography variant="h6">Active Anomalies</Typography>
              </Box>
              <Typography variant="h3" color="warning.main">
                {anomalies.length}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Last 7 days
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUpIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Avg Confidence</Typography>
              </Box>
              <Typography variant="h3" color="primary.main">
                {(avgConfidence * 100).toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Detection accuracy
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ErrorIcon color="error" sx={{ mr: 1 }} />
                <Typography variant="h6">High Severity</Typography>
              </Box>
              <Typography variant="h3" color="error.main">
                {highSeverityCount}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Require immediate attention
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingDownIcon color="success" sx={{ mr: 1 }} />
                <Typography variant="h6">Total Impact</Typography>
              </Box>
              <Typography variant="h3" color="success.main">
                ${totalImpact.toFixed(0)}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Detected cost impact
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* System Status */}
      {systemStatus && (
        <Alert 
          severity={systemStatus.system_status.overall_status === 'operational' ? 'success' : 'warning'}
          sx={{ mb: 3 }}
        >
          <Typography variant="body2">
            System Status: {systemStatus.system_status.overall_status.toUpperCase()} | 
            Uptime: {systemStatus.system_status.uptime_percentage}% | 
            Models: {systemStatus.model_status.deployed_models}/{systemStatus.model_status.total_models} deployed | 
            Avg Accuracy: {(systemStatus.model_status.average_accuracy * 100).toFixed(1)}%
          </Typography>
        </Alert>
      )}

      {/* Tabs */}
      <Card>
        <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Anomalies" />
          <Tab label="Forecast" />
          <Tab label="Service Analysis" />
          <Tab label="Trends" />
        </Tabs>

        <CardContent>
          {/* Anomalies Tab */}
          {activeTab === 0 && (
            <Box>
              {anomalies.length === 0 ? (
                <Alert severity="success" icon={<CheckCircleIcon />}>
                  No anomalies detected in the last 7 days. Your costs are following normal patterns.
                </Alert>
              ) : (
                <Grid container spacing={2}>
                  {anomalies.map((anomaly) => (
                    <Grid item xs={12} key={anomaly.anomaly_id}>
                      <Card 
                        variant="outlined" 
                        sx={{ 
                          cursor: 'pointer',
                          '&:hover': { backgroundColor: 'action.hover' }
                        }}
                        onClick={() => openAnomalyDetails(anomaly.anomaly_id)}
                      >
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                            <Box>
                              <Typography variant="h6" gutterBottom>
                                {anomaly.affected_services.join(', ')} Cost Anomaly
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                {format(parseISO(anomaly.detection_timestamp), 'MMM dd, yyyy HH:mm')}
                              </Typography>
                            </Box>
                            <Box sx={{ textAlign: 'right' }}>
                              <Chip 
                                label={`${(anomaly.confidence_score * 100).toFixed(0)}% confidence`}
                                color={getConfidenceColor(anomaly.confidence_score)}
                                size="small"
                                sx={{ mb: 1 }}
                              />
                              <Typography variant="h6" color="error.main">
                                +${anomaly.estimated_impact_usd.toFixed(2)}
                              </Typography>
                            </Box>
                          </Box>
                          
                          <Typography variant="body1" sx={{ mb: 2 }}>
                            {anomaly.description}
                          </Typography>
                          
                          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            <Chip 
                              label={anomaly.severity.toUpperCase()}
                              color={getRiskColor(anomaly.severity)}
                              size="small"
                            />
                            <Chip 
                              label={`Score: ${anomaly.anomaly_score.toFixed(2)}`}
                              variant="outlined"
                              size="small"
                            />
                            {anomaly.affected_regions.map(region => (
                              <Chip 
                                key={region}
                                label={region}
                                variant="outlined"
                                size="small"
                              />
                            ))}
                          </Box>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              )}
            </Box>
          )}

          {/* Forecast Tab */}
          {activeTab === 1 && (
            <ForecastVisualization 
              accountId={accountId}
              onForecastGenerated={handleForecastGenerated}
            />
          )}

          {/* Service Analysis Tab */}
          {activeTab === 2 && (
            <Box>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Typography variant="h6" gutterBottom>
                    Anomalies by Service
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={prepareAnomalyServiceData()}
                        dataKey="count"
                        nameKey="service"
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={({ service, count }) => `${service}: ${count}`}
                      >
                        {prepareAnomalyServiceData().map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </Grid>
                
                <Grid item xs={12} md={6}>
                  <Typography variant="h6" gutterBottom>
                    Cost Impact by Service
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={prepareAnomalyServiceData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="service" />
                      <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                      <RechartsTooltip 
                        formatter={(value: number) => [`$${value.toFixed(2)}`, 'Impact']}
                      />
                      <Bar dataKey="impact" fill="#1976d2" />
                    </BarChart>
                  </ResponsiveContainer>
                </Grid>
              </Grid>
            </Box>
          )}

          {/* Trends Tab */}
          {activeTab === 3 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Anomaly Detection Trends
              </Typography>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={prepareAnomalyTrendData()}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <RechartsTooltip />
                  <Line 
                    type="monotone" 
                    dataKey="count" 
                    stroke="#1976d2" 
                    strokeWidth={2}
                    name="Anomalies Detected"
                  />
                </LineChart>
              </ResponsiveContainer>

              {systemStatus && (
                <Grid container spacing={2} sx={{ mt: 2 }}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="subtitle1" gutterBottom>
                      24-Hour Statistics
                    </Typography>
                    <List>
                      <ListItem>
                        <ListItemText
                          primary="Anomalies Detected"
                          secondary={systemStatus.statistics.anomalies_detected_24h}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="Alerts Generated"
                          secondary={systemStatus.statistics.alerts_generated_24h}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="API Requests"
                          secondary={systemStatus.statistics.api_requests_24h.toLocaleString()}
                        />
                      </ListItem>
                    </List>
                  </Grid>
                  
                  <Grid item xs={12} md={6}>
                    <Typography variant="subtitle1" gutterBottom>
                      Performance Metrics
                    </Typography>
                    <List>
                      <ListItem>
                        <ListItemText
                          primary="Average Response Time"
                          secondary={`${systemStatus.statistics.average_response_time_ms.toFixed(1)}ms`}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="CPU Usage"
                          secondary={`${systemStatus.performance_metrics.cpu_usage_percent.toFixed(1)}%`}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="Memory Usage"
                          secondary={`${systemStatus.performance_metrics.memory_usage_percent.toFixed(1)}%`}
                        />
                      </ListItem>
                    </List>
                  </Grid>
                </Grid>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Configuration Dialog */}
      <Dialog 
        open={configurationOpen} 
        onClose={() => setConfigurationOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>Anomaly Detection Configuration</DialogTitle>
        <DialogContent>
          <AnomalyConfigurationComponent 
            accountId={accountId}
            onConfigurationChange={handleConfigurationChange}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigurationOpen(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Explanation Viewer */}
      <ExplanationViewer
        anomalyId={selectedAnomalyId}
        open={explanationOpen}
        onClose={() => {
          setExplanationOpen(false);
          setSelectedAnomalyId(null);
        }}
      />
    </Box>
  );
};

export default AnomalyDashboard;