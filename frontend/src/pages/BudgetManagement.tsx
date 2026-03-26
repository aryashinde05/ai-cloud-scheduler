import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  LinearProgress,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Alert,
} from '@mui/material';
import { motion } from 'framer-motion';
import {
  Add,
  Edit,
  Delete,
  Warning,
  CheckCircle,
  Error as MuiError,
  Notifications,
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
  LineChart,
  Line,
} from 'recharts';
import numeral from 'numeral';
import { useNavigate } from 'react-router-dom';
import { SkeletonLoader } from '../components/Loading';

const BudgetManagement: React.FC = () => {
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedBudget, setSelectedBudget] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [noAws, setNoAws] = useState(false);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [newBudget, setNewBudget] = useState({
    name: '',
    amount: '',
    period: 'monthly',
    team: '',
    alerts: [75, 90],
  });
  const navigate = useNavigate();

  useEffect(() => {
    loadBudgets();
  }, []);

  const loadBudgets = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/aws/budgets', { credentials: 'include' });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        if (response.status === 400) { setNoAws(true); setLoading(false); return; }
        throw new window.Error(err.detail || 'Failed to load budgets');
      }
      const data = await response.json();
      setBudgets(data.budgets || []);
      setLoading(false);
    } catch (error) {
      console.error('Error loading budgets:', error);
      setLoading(false);
    }
  };

  const handleCreateBudget = async () => {
    try {
      const res = await fetch('/api/v1/aws/budgets', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newBudget),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new window.Error(errorData.detail || 'Failed');
      }
      setCreateDialogOpen(false);
      setNewBudget({ name: '', amount: '', period: 'monthly', team: '', alerts: [75, 90] });
      loadBudgets();
    } catch (e: any) {
      console.error('Create budget error:', e);
    }
  };

  const handleDeleteBudget = async (budgetId: string) => {
    try {
      await fetch(`/api/v1/aws/budgets/${encodeURIComponent(budgetId)}`, {
        method: 'DELETE', credentials: 'include',
      });
      loadBudgets();
    } catch (e) {
      console.error('Delete budget error:', e);
    }
  };
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good': return '#4caf50';
      case 'warning': return '#ff9800';
      case 'critical': return '#f44336';
      default: return '#9e9e9e';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good': return <CheckCircle sx={{ color: '#4caf50', fontSize: 20 }} />;
      case 'warning': return <Warning sx={{ color: '#ff9800', fontSize: 20 }} />;
      case 'critical': return <MuiError sx={{ color: '#f44336', fontSize: 20 }} />;
      default: return <CheckCircle sx={{ color: '#9e9e9e', fontSize: 20 }} />;
    }
  };

  const handleEditBudget = (budget: any) => {
    setSelectedBudget(budget);
    setEditDialogOpen(true);
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" sx={{ mb: 4, fontWeight: 700 }}>Budget Management</Typography>
        <SkeletonLoader variant="table" count={5} />
      </Box>
    );
  }

  if (noAws) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <CloudOff sx={{ fontSize: 80, color: 'text.secondary', mb: 3 }} />
        <Typography variant="h4" sx={{ mb: 2, fontWeight: 700 }}>No AWS Account Connected</Typography>
        <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
          Connect your AWS account to see and manage your AWS budgets.
        </Typography>
        <Button variant="contained" size="large" onClick={() => navigate('/onboarding')}>
          Connect AWS Account
        </Button>
      </Box>
    );
  }

  const totalBudget = budgets.reduce((sum, budget) => sum + budget.amount, 0);
  const totalSpent = budgets.reduce((sum, budget) => sum + budget.spent, 0);
  const overallUtilization = totalBudget > 0 ? (totalSpent / totalBudget) * 100 : 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>Budget Management</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => setCreateDialogOpen(true)}>
          Create Budget
        </Button>
      </Box>

      {/* Budget Overview Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Total Budget</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{numeral(totalBudget).format('$0,0')}</Typography>
              <Chip label={`${budgets.length} active budgets`} size="small" sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Total Spent</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{numeral(totalSpent).format('$0,0')}</Typography>
              <Chip label={`${overallUtilization.toFixed(1)}% utilized`} size="small"
                sx={{
                  backgroundColor: overallUtilization > 90 ? 'rgba(244, 67, 54, 0.2)' : 'rgba(76, 175, 80, 0.2)',
                  color: overallUtilization > 90 ? '#f44336' : '#4caf50'
                }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Remaining Budget</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{numeral(totalBudget - totalSpent).format('$0,0')}</Typography>
              <Chip label={totalBudget > 0 ? `${((totalBudget - totalSpent) / totalBudget * 100).toFixed(1)}% remaining` : 'N/A'} size="small"
                sx={{ backgroundColor: 'rgba(76, 175, 80, 0.2)', color: '#4caf50' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Active Alerts</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, color: '#ff9800' }}>
                {budgets.filter(b => b.alerts && b.alerts.some((a: any) => a.triggered)).length}
              </Typography>
              <Chip label="Need attention" size="small" sx={{ backgroundColor: 'rgba(255, 152, 0, 0.2)', color: '#ff9800' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Budget List */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>Budget Details</Typography>
              {budgets.length > 0 ? (
                <TableContainer component={Paper} sx={{ backgroundColor: 'transparent' }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Budget Name</TableCell>
                        <TableCell>Team</TableCell>
                        <TableCell align="right">Amount</TableCell>
                        <TableCell align="right">Spent</TableCell>
                        <TableCell align="center">Utilization</TableCell>
                        <TableCell align="center">Status</TableCell>
                        <TableCell align="center">Alerts</TableCell>
                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {budgets.map((budget) => (
                        <TableRow key={budget.id}>
                          <TableCell component="th" scope="row">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{budget.name}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>{budget.period}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={budget.team || 'General'} size="small" sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3' }} />
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{numeral(budget.amount).format('$0,0')}</Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{numeral(budget.spent).format('$0,0')}</Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ width: '100%', mr: 1 }}>
                              <LinearProgress variant="determinate" value={Math.min(budget.utilization, 100)}
                                sx={{
                                  height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.1)',
                                  '& .MuiLinearProgress-bar': { backgroundColor: getStatusColor(budget.status) }
                                }} />
                              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{budget.utilization}%</Typography>
                            </Box>
                          </TableCell>
                          <TableCell align="center">{getStatusIcon(budget.status)}</TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.5 }}>
                              {(budget.alerts || []).map((alert: any, index: number) => (
                                <Chip key={index} label={`${alert.threshold}%`} size="small"
                                  sx={{
                                    backgroundColor: alert.triggered ? 'rgba(244, 67, 54, 0.2)' : 'rgba(158, 158, 158, 0.2)',
                                    color: alert.triggered ? '#f44336' : '#9e9e9e', fontSize: '0.7rem'
                                  }} />
                              ))}
                            </Box>
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
                              <Tooltip title="Edit Budget">
                                <IconButton size="small" onClick={() => handleEditBudget(budget)}><Edit sx={{ fontSize: 16 }} /></IconButton>
                              </Tooltip>
                              <Tooltip title="Delete Budget">
                                <IconButton size="small" onClick={() => handleDeleteBudget(budget.id)}>
                                  <Delete sx={{ fontSize: 16, color: '#f44336' }} />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Alert severity="info">
                  No AWS Budgets configured. Create budgets in the AWS Console to track and manage your cloud spending.
                </Alert>
              )}
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Create Budget Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Budget</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField fullWidth label="Budget Name" value={newBudget.name}
                onChange={(e) => setNewBudget({ ...newBudget, name: e.target.value })} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth label="Amount" type="number" value={newBudget.amount}
                onChange={(e) => setNewBudget({ ...newBudget, amount: e.target.value })}
                InputProps={{ startAdornment: '$' }} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Period</InputLabel>
                <Select value={newBudget.period} label="Period"
                  onChange={(e) => setNewBudget({ ...newBudget, period: e.target.value })}>
                  <MenuItem value="monthly">Monthly</MenuItem>
                  <MenuItem value="quarterly">Quarterly</MenuItem>
                  <MenuItem value="annual">Annual</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth label="Team" value={newBudget.team}
                onChange={(e) => setNewBudget({ ...newBudget, team: e.target.value })} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateBudget} variant="contained">Create Budget</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default BudgetManagement;