import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Button,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
  Schedule as TimelineIcon,
  Security as SecurityIcon,
  Assessment as ReportIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';

// Types
interface OptimizationAction {
  action_id: string;
  action_type: string;
  resource_id: string;
  resource_type: string;
  estimated_monthly_savings: number;
  risk_level: 'low' | 'medium' | 'high';
  requires_approval: boolean;
  scheduled_execution_time: string;
  safety_checks_passed: boolean;
  execution_status: 'pending' | 'executing' | 'completed' | 'failed' | 'rolled_back';
  created_at: string;
  updated_at: string;
}

interface AutomationStats {
  total_actions: number;
  pending_actions: number;
  completed_actions: number;
  failed_actions: number;
  total_savings: number;
  monthly_savings: number;
  automation_enabled: boolean;
  last_execution: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`automation-tabpanel-${index}`}
      aria-labelledby={`automation-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const AutomationDashboard: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [selectedAction, setSelectedAction] = useState<OptimizationAction | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const queryClient = useQueryClient();

  // Fetch automation statistics
  const { data: stats, isLoading: statsLoading } = useQuery<AutomationStats>(
    'automation-stats',
    async () => {
      const response = await fetch('/api/v1/automation/stats', { credentials: 'include' });
      if (!response.ok) throw new Error('Failed to fetch automation stats');
      return response.json();
    },
    { refetchInterval: 30000 }
  );

  // Fetch optimization actions
  const { data: actions, isLoading: actionsLoading } = useQuery<OptimizationAction[]>(
    'optimization-actions',
    async () => {
      const response = await fetch('/api/v1/automation/actions', { credentials: 'include' });
      if (!response.ok) throw new Error('Failed to fetch optimization actions');
      return response.json();
    },
    { refetchInterval: 30000 }
  );

  // Toggle automation mutation (no-op — just UI state for now)
  const toggleAutomationMutation = useMutation(
    async (enabled: boolean) => enabled,
    {
      onSuccess: () => {
        queryClient.invalidateQueries('automation-stats');
        toast.success('Automation settings updated');
      },
    }
  );

  // Execute action mutation
  const executeActionMutation = useMutation(
    async (actionId: string) => {
      const response = await fetch('/api/v1/automation/actions/execute', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_ids: [actionId] }),
      });
      if (!response.ok) throw new Error('Failed to execute action');
      return response.json();
    },
    {
      onSuccess: (data: any) => {
        queryClient.invalidateQueries('optimization-actions');
        const result = data?.results?.[0];
        if (result?.status === 'success') toast.success(result.message || 'Action executed');
        else toast.error(result?.message || 'Action could not be executed');
      },
      onError: () => { toast.error('Failed to execute action'); },
    }
  );

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleActionClick = (action: OptimizationAction) => {
    setSelectedAction(action);
    setDetailsOpen(true);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'executing': return 'warning';
      case 'rolled_back': return 'error';
      default: return 'default';
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low': return 'success';
      case 'medium': return 'warning';
      case 'high': return 'error';
      default: return 'default';
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  if (statsLoading || actionsLoading) {
    return (
      <Box sx={{ width: '100%', mt: 2 }}>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
            Automation Dashboard
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor and manage automated cost optimization actions
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControlLabel
            control={
              <Switch
                checked={stats?.automation_enabled || false}
                onChange={(e) => toggleAutomationMutation.mutate(e.target.checked)}
                color="primary"
              />
            }
            label="Automation Enabled"
          />
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => {
              queryClient.invalidateQueries('automation-stats');
              queryClient.invalidateQueries('optimization-actions');
            }}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<SettingsIcon />}
            href="/automation/settings"
          >
            Settings
          </Button>
        </Box>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TimelineIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Total Actions</Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {stats?.total_actions || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                All time executions
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <ScheduleIcon color="warning" sx={{ mr: 1 }} />
                <Typography variant="h6">Pending</Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {stats?.pending_actions || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Awaiting execution
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <CheckIcon color="success" sx={{ mr: 1 }} />
                <Typography variant="h6">Completed</Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {stats?.completed_actions || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Successfully executed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <ReportIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Monthly Savings</Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600, color: 'success.main' }}>
                {formatCurrency(stats?.monthly_savings || 0)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                This month's optimization
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Status Alert */}
      {!stats?.automation_enabled && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Automation is currently disabled. Enable it to start automatic cost optimization.
        </Alert>
      )}

      {/* Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Recent Actions" />
            <Tab label="Pending Approvals" />
            <Tab label="Failed Actions" />
            <Tab label="Scheduled Actions" />
          </Tabs>
        </Box>

        <TabPanel value={tabValue} index={0}>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Action Type</TableCell>
                  <TableCell>Resource</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Risk Level</TableCell>
                  <TableCell>Estimated Savings</TableCell>
                  <TableCell>Execution Time</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {actions?.slice(0, 10).map((action) => (
                  <TableRow key={action.action_id} hover>
                    <TableCell>{action.action_type.replace('_', ' ')}</TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{action.resource_id}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {action.resource_type}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={action.execution_status}
                        color={getStatusColor(action.execution_status) as any}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={action.risk_level}
                        color={getRiskColor(action.risk_level) as any}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{formatCurrency(action.estimated_monthly_savings)}</TableCell>
                    <TableCell>
                      {new Date(action.scheduled_execution_time).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => handleActionClick(action)}
                      >
                        <SettingsIcon />
                      </IconButton>
                      {action.execution_status === 'pending' && (
                        <IconButton
                          size="small"
                          onClick={() => executeActionMutation.mutate(action.action_id)}
                          disabled={executeActionMutation.isLoading}
                        >
                          <PlayIcon />
                        </IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Action Type</TableCell>
                  <TableCell>Resource</TableCell>
                  <TableCell>Risk Level</TableCell>
                  <TableCell>Estimated Savings</TableCell>
                  <TableCell>Scheduled Time</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {actions?.filter(action => action.requires_approval && action.execution_status === 'pending').map((action) => (
                  <TableRow key={action.action_id} hover>
                    <TableCell>{action.action_type.replace('_', ' ')}</TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{action.resource_id}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {action.resource_type}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={action.risk_level}
                        color={getRiskColor(action.risk_level) as any}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{formatCurrency(action.estimated_monthly_savings)}</TableCell>
                    <TableCell>
                      {new Date(action.scheduled_execution_time).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="contained"
                        color="success"
                        sx={{ mr: 1 }}
                        onClick={() => executeActionMutation.mutate(action.action_id)}
                      >
                        Approve
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="error"
                      >
                        Reject
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Action Type</TableCell>
                  <TableCell>Resource</TableCell>
                  <TableCell>Error</TableCell>
                  <TableCell>Failed Time</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {actions?.filter(action => action.execution_status === 'failed').map((action) => (
                  <TableRow key={action.action_id} hover>
                    <TableCell>{action.action_type.replace('_', ' ')}</TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{action.resource_id}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {action.resource_type}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="error">
                        Execution failed - check logs
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {new Date(action.updated_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => executeActionMutation.mutate(action.action_id)}
                      >
                        Retry
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Action Type</TableCell>
                  <TableCell>Resource</TableCell>
                  <TableCell>Risk Level</TableCell>
                  <TableCell>Estimated Savings</TableCell>
                  <TableCell>Scheduled Time</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {actions?.filter(action => 
                  action.execution_status === 'pending' && 
                  new Date(action.scheduled_execution_time) > new Date()
                ).map((action) => (
                  <TableRow key={action.action_id} hover>
                    <TableCell>{action.action_type.replace('_', ' ')}</TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{action.resource_id}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {action.resource_type}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={action.risk_level}
                        color={getRiskColor(action.risk_level) as any}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{formatCurrency(action.estimated_monthly_savings)}</TableCell>
                    <TableCell>
                      {new Date(action.scheduled_execution_time).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => handleActionClick(action)}
                      >
                        <SettingsIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </TabPanel>
      </Card>

      {/* Action Details Dialog */}
      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Action Details: {selectedAction?.action_type.replace('_', ' ')}
        </DialogTitle>
        <DialogContent>
          {selectedAction && (
            <Box sx={{ mt: 2 }}>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Resource ID
                  </Typography>
                  <Typography variant="body1">{selectedAction.resource_id}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Resource Type
                  </Typography>
                  <Typography variant="body1">{selectedAction.resource_type}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Risk Level
                  </Typography>
                  <Chip
                    label={selectedAction.risk_level}
                    color={getRiskColor(selectedAction.risk_level) as any}
                    size="small"
                  />
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Status
                  </Typography>
                  <Chip
                    label={selectedAction.execution_status}
                    color={getStatusColor(selectedAction.execution_status) as any}
                    size="small"
                  />
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Estimated Monthly Savings
                  </Typography>
                  <Typography variant="body1" color="success.main">
                    {formatCurrency(selectedAction.estimated_monthly_savings)}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Safety Checks
                  </Typography>
                  <Chip
                    label={selectedAction.safety_checks_passed ? 'Passed' : 'Failed'}
                    color={selectedAction.safety_checks_passed ? 'success' : 'error'}
                    size="small"
                  />
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Scheduled Execution Time
                  </Typography>
                  <Typography variant="body1">
                    {new Date(selectedAction.scheduled_execution_time).toLocaleString()}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailsOpen(false)}>Close</Button>
          {selectedAction?.execution_status === 'pending' && (
            <Button
              variant="contained"
              onClick={() => {
                executeActionMutation.mutate(selectedAction.action_id);
                setDetailsOpen(false);
              }}
            >
              Execute Now
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AutomationDashboard;