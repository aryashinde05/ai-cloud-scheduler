import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
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
  LinearProgress,
  Alert,
} from '@mui/material';
import { motion } from 'framer-motion';
import {
  Add,
  Download,
  Schedule,
  Visibility,
  Delete,
  Assessment,
  PictureAsPdf,
  TableChart,
  CloudOff,
} from '@mui/icons-material';
import numeral from 'numeral';
import { useNavigate } from 'react-router-dom';

const reportTemplates = [
  { id: 'cost_summary', name: 'Cost Summary Report', description: 'Comprehensive cost breakdown and trends' },
  { id: 'budget_analysis', name: 'Budget Analysis Report', description: 'Budget performance and variance analysis' },
  { id: 'optimization', name: 'Optimization Report', description: 'Cost optimization opportunities and recommendations' },
  { id: 'compliance', name: 'Compliance Report', description: 'Tagging compliance and governance status' },
  { id: 'chargeback', name: 'Chargeback Report', description: 'Cost allocation by teams and projects' },
];

const Reports: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [noAws, setNoAws] = useState(false);
  const [reports, setReports] = useState<any[]>([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newReport, setNewReport] = useState({
    name: '',
    type: '',
    schedule: 'monthly',
    recipients: '',
    format: 'PDF',
  });
  const navigate = useNavigate();

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      setLoading(true);
      const [summaryRes, oppsRes, inventoryRes] = await Promise.all([
        fetch('/api/v1/reports/summary', { credentials: 'include' }),
        fetch('/api/v1/reports/optimization-opportunities', { credentials: 'include' }),
        fetch('/api/v1/reports/resource-inventory', { credentials: 'include' }),
      ]);
      if (!summaryRes.ok) {
        const err = await summaryRes.json().catch(() => ({}));
        if (summaryRes.status === 400) { setNoAws(true); setLoading(false); return; }
        throw new Error(err.detail || 'Failed');
      }
      const summary = await summaryRes.json();
      const opps = await oppsRes.json().catch(() => ({ opportunities: [] }));
      const inventory = await inventoryRes.json().catch(() => ({}));
      // Build a synthetic "reports" list from real data
      const syntheticReports = [
        {
          id: 'cost-summary', name: 'Cost Summary', type: 'cost_summary',
          schedule: 'on-demand', status: 'active', format: 'Live',
          lastRun: summary.data_freshness, nextRun: null,
          data: summary,
        },
        {
          id: 'optimization', name: 'Optimization Opportunities', type: 'optimization',
          schedule: 'on-demand', status: 'active', format: 'Live',
          lastRun: summary.data_freshness, nextRun: null,
          data: opps,
        },
        {
          id: 'inventory', name: 'Resource Inventory', type: 'inventory',
          schedule: 'on-demand', status: 'active', format: 'Live',
          lastRun: summary.data_freshness, nextRun: null,
          data: inventory,
        },
      ];
      setReports(syntheticReports);
      setLoading(false);
    } catch (error) {
      console.error('Error loading reports:', error);
      setLoading(false);
    }
  };

  const handleCreateReport = () => {
    setCreateDialogOpen(false);
    setNewReport({ name: '', type: '', schedule: 'monthly', recipients: '', format: 'PDF' });
  };

  const handleDownloadReport = (reportId: string) => {
    // Open the relevant API endpoint in a new tab for download
    const urlMap: Record<string, string> = {
      'cost-summary': '/api/v1/reports/summary',
      'optimization': '/api/v1/reports/optimization-opportunities',
      'inventory': '/api/v1/reports/resource-inventory',
    };
    const url = urlMap[reportId];
    if (url) window.open(url, '_blank');
  };

  const handleDeleteReport = (reportId: string) => {
    setReports(prev => prev.filter(r => r.id !== reportId));
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return '#4caf50';
      case 'paused': return '#ff9800';
      case 'error': return '#f44336';
      default: return '#9e9e9e';
    }
  };

  const getFormatIcon = (format: string) => {
    switch (format) {
      case 'PDF': return <PictureAsPdf sx={{ fontSize: 16 }} />;
      case 'Excel': return <TableChart sx={{ fontSize: 16 }} />;
      default: return <Assessment sx={{ fontSize: 16 }} />;
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" sx={{ mb: 4, fontWeight: 700 }}>Reports & Analytics</Typography>
        <LinearProgress />
        <Typography variant="body2" sx={{ mt: 2, textAlign: 'center' }}>Loading reports...</Typography>
      </Box>
    );
  }

  if (noAws) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <CloudOff sx={{ fontSize: 80, color: 'text.secondary', mb: 3 }} />
        <Typography variant="h4" sx={{ mb: 2, fontWeight: 700 }}>No AWS Account Connected</Typography>
        <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
          Connect your AWS account to generate cost reports and analytics.
        </Typography>
        <Button variant="contained" size="large" onClick={() => navigate('/onboarding')}>
          Connect AWS Account
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>Reports & Analytics</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => setCreateDialogOpen(true)}>
          Create Report
        </Button>
      </Box>

      {/* Report Statistics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Active Reports</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                {reports.filter(r => r.status === 'active').length}
              </Typography>
              <Chip label="Scheduled" size="small" sx={{ backgroundColor: 'rgba(76, 175, 80, 0.2)', color: '#4caf50' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Total Reports</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{reports.length}</Typography>
              <Chip label="Configured" size="small" sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Templates Available</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{reportTemplates.length}</Typography>
              <Chip label="Ready to use" size="small" sx={{ backgroundColor: 'rgba(156, 39, 176, 0.2)', color: '#9c27b0' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Data Source</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>AWS</Typography>
              <Chip label="Connected" size="small" sx={{ backgroundColor: 'rgba(76, 175, 80, 0.2)', color: '#4caf50' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Reports Table */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>Scheduled Reports</Typography>
              {reports.length > 0 ? (
                <TableContainer component={Paper} sx={{ backgroundColor: 'transparent' }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Report Name</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Schedule</TableCell>
                        <TableCell>Last Run</TableCell>
                        <TableCell>Next Run</TableCell>
                        <TableCell align="center">Status</TableCell>
                        <TableCell align="center">Format</TableCell>
                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {reports.map((report) => (
                        <TableRow key={report.id}>
                          <TableCell component="th" scope="row">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{report.name}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={(report.type || '').replace('_', ' ')} size="small"
                              sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3', textTransform: 'capitalize' }} />
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <Schedule sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                              <Typography variant="body2">{report.schedule}</Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{report.lastRun ? new Date(report.lastRun).toLocaleDateString() : '—'}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{report.nextRun ? new Date(report.nextRun).toLocaleDateString() : '—'}</Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Chip label={report.status} size="small"
                              sx={{ backgroundColor: `${getStatusColor(report.status)}20`, color: getStatusColor(report.status), textTransform: 'capitalize' }} />
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              {getFormatIcon(report.format)}
                              <Typography variant="body2" sx={{ ml: 1 }}>{report.format}</Typography>
                            </Box>
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
                              <Tooltip title="Download Latest">
                                <IconButton size="small" onClick={() => handleDownloadReport(report.id)}>
                                  <Download sx={{ fontSize: 16 }} />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="View Report">
                                <IconButton size="small"><Visibility sx={{ fontSize: 16 }} /></IconButton>
                              </Tooltip>
                              <Tooltip title="Delete Report">
                                <IconButton size="small" onClick={() => handleDeleteReport(report.id)}>
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
                  No scheduled reports yet. Create a report from one of the available templates to start generating automated cost reports from your AWS data.
                </Alert>
              )}
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Create Report Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Create New Report</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField fullWidth label="Report Name" value={newReport.name}
                onChange={(e) => setNewReport({ ...newReport, name: e.target.value })} />
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Report Type</InputLabel>
                <Select value={newReport.type} label="Report Type"
                  onChange={(e) => setNewReport({ ...newReport, type: e.target.value })}>
                  {reportTemplates.map((template) => (
                    <MenuItem key={template.id} value={template.id}>
                      <Box>
                        <Typography variant="body2">{template.name}</Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>{template.description}</Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Schedule</InputLabel>
                <Select value={newReport.schedule} label="Schedule"
                  onChange={(e) => setNewReport({ ...newReport, schedule: e.target.value })}>
                  <MenuItem value="daily">Daily</MenuItem>
                  <MenuItem value="weekly">Weekly</MenuItem>
                  <MenuItem value="monthly">Monthly</MenuItem>
                  <MenuItem value="quarterly">Quarterly</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Format</InputLabel>
                <Select value={newReport.format} label="Format"
                  onChange={(e) => setNewReport({ ...newReport, format: e.target.value })}>
                  <MenuItem value="PDF">PDF</MenuItem>
                  <MenuItem value="Excel">Excel</MenuItem>
                  <MenuItem value="CSV">CSV</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth label="Recipients (comma-separated emails)" value={newReport.recipients}
                onChange={(e) => setNewReport({ ...newReport, recipients: e.target.value })}
                placeholder="user1@company.com, user2@company.com" />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateReport} variant="contained">Create Report</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Reports;