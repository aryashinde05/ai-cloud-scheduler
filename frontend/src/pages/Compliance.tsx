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
  LinearProgress,
  Tabs,
  Tab,
  Alert,
} from '@mui/material';
import { motion } from 'framer-motion';
import {
  Security,
  Warning,
  CheckCircle,
  Error as ErrorIcon,
  Refresh,
  Download,
  Visibility,
  Policy,
  Assessment,
  CloudOff,
} from '@mui/icons-material';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
} from 'recharts';
import numeral from 'numeral';
import { useNavigate } from 'react-router-dom';
import { SkeletonLoader } from '../components/Loading';

const Compliance: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [noAws, setNoAws] = useState(false);
  const [complianceOverview, setComplianceOverview] = useState<any>(null);
  const [taggingCompliance, setTaggingCompliance] = useState<any[]>([]);
  const [policyViolations, setPolicyViolations] = useState<any[]>([]);
  const [complianceByService, setComplianceByService] = useState<any[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    loadComplianceData();
  }, []);

  const loadComplianceData = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/compliance', { credentials: 'include' });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        if (response.status === 400) { setNoAws(true); setLoading(false); return; }
        throw new Error(err.detail || 'Failed');
      }
      const data = await response.json();
      setComplianceOverview(data.overview || null);
      setTaggingCompliance(data.taggingCompliance || []);
      setPolicyViolations(data.policyViolations || []);
      setComplianceByService(data.complianceByService || []);
      setLoading(false);
    } catch (error) {
      console.error('Error loading compliance data:', error);
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return '#f44336';
      case 'high': return '#ff5722';
      case 'medium': return '#ff9800';
      case 'low': return '#ffc107';
      default: return '#9e9e9e';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <ErrorIcon sx={{ color: '#f44336', fontSize: 16 }} />;
      case 'high': return <Warning sx={{ color: '#ff5722', fontSize: 16 }} />;
      case 'medium': return <Warning sx={{ color: '#ff9800', fontSize: 16 }} />;
      case 'low': return <Warning sx={{ color: '#ffc107', fontSize: 16 }} />;
      default: return <CheckCircle sx={{ color: '#4caf50', fontSize: 16 }} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return '#f44336';
      case 'remediated': return '#4caf50';
      case 'in_progress': return '#ff9800';
      default: return '#9e9e9e';
    }
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" sx={{ mb: 4, fontWeight: 700 }}>Compliance & Governance</Typography>
        <SkeletonLoader variant="table" count={6} />
      </Box>
    );
  }

  if (noAws) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <CloudOff sx={{ fontSize: 80, color: 'text.secondary', mb: 3 }} />
        <Typography variant="h4" sx={{ mb: 2, fontWeight: 700 }}>No AWS Account Connected</Typography>
        <Typography variant="body1" sx={{ mb: 4, color: 'text.secondary' }}>
          Connect your AWS account to scan resources for tagging compliance and security violations.
        </Typography>
        <Button variant="contained" size="large" onClick={() => navigate('/onboarding')}>
          Connect AWS Account
        </Button>
      </Box>
    );
  }

  const openViolations = policyViolations.filter(v => v.status === 'open').length;
  const criticalViolations = policyViolations.filter(v => v.severity === 'critical' && v.status === 'open').length;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>Compliance & Governance</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button variant="outlined" startIcon={<Refresh />} onClick={loadComplianceData}>Refresh Scan</Button>
          <Button variant="outlined" startIcon={<Download />}>Export Report</Button>
        </Box>
      </Box>

      {criticalViolations > 0 && (
        <Alert severity="error" sx={{ mb: 4 }}>
          You have {criticalViolations} critical compliance violation{criticalViolations > 1 ? 's' : ''} that require immediate attention.
        </Alert>
      )}

      {/* Compliance Overview Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Overall Compliance</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{complianceOverview?.overallScore || 0}%</Typography>
              <LinearProgress variant="determinate" value={complianceOverview?.overallScore || 0}
                sx={{
                  height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.1)',
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: (complianceOverview?.overallScore || 0) > 90 ? '#4caf50' :
                      (complianceOverview?.overallScore || 0) > 75 ? '#ff9800' : '#f44336',
                  }
                }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Tagging Compliance</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{complianceOverview?.taggingCompliance || 0}%</Typography>
              <Chip label={`${complianceOverview?.compliantResources || 0}/${complianceOverview?.totalResources || 0} resources`} size="small"
                sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Policy Violations</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1, color: openViolations > 0 ? '#f44336' : '#4caf50' }}>
                {openViolations}
              </Typography>
              <Chip label="Open violations" size="small" sx={{ backgroundColor: 'rgba(244, 67, 54, 0.2)', color: '#f44336' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} md={3}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ color: 'text.secondary', mb: 1 }}>Security Score</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>{complianceOverview?.securityCompliance || 0}%</Typography>
              <Chip label={(complianceOverview?.securityCompliance || 0) > 90 ? 'Good standing' : 'Needs attention'} size="small"
                sx={{ backgroundColor: 'rgba(76, 175, 80, 0.2)', color: '#4caf50' }} />
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Compliance Charts */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={8}>
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>Tagging Compliance by Team</Typography>
              {taggingCompliance.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={taggingCompliance}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="team" stroke="#b0bec5" />
                    <YAxis stroke="#b0bec5" />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: '#1a1d3a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                      formatter={(value: any, name: any) => [
                        name === 'compliant' ? `${value} compliant` : `${value} total`, ''
                      ]}
                    />
                    <Bar dataKey="total" fill="rgba(158, 158, 158, 0.5)" name="Total Resources" />
                    <Bar dataKey="compliant" fill="#4caf50" name="Compliant Resources" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Typography variant="body2" sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
                  No tagging data available.
                </Typography>
              )}
            </CardContent></Card>
          </motion.div>
        </Grid>

        <Grid item xs={12} lg={4}>
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6 }}>
            <Card><CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>Compliance by Service</Typography>
              {complianceByService.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={complianceByService} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                        paddingAngle={5} dataKey="compliant">
                        {complianceByService.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip
                        contentStyle={{ backgroundColor: '#1a1d3a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                        formatter={(value: any, name: any, props: any) => [
                          `${value}% compliant`, props.payload.service
                        ]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <Box sx={{ mt: 2 }}>
                    {complianceByService.map((service) => (
                      <Box key={service.service} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <Box sx={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: service.color, mr: 1 }} />
                        <Typography variant="body2" sx={{ flexGrow: 1, fontSize: '0.8rem' }}>{service.service}</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{service.compliant}%</Typography>
                      </Box>
                    ))}
                  </Box>
                </>
              ) : (
                <Typography variant="body2" sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
                  No service data available.
                </Typography>
              )}
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Compliance Details */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <Card><CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6">Compliance Details</Typography>
                <Tabs value={selectedTab} onChange={(e, newValue) => setSelectedTab(newValue)}>
                  <Tab label="Policy Violations" />
                  <Tab label="Tagging Issues" />
                  <Tab label="Security Findings" />
                </Tabs>
              </Box>

              {selectedTab === 0 && (
                policyViolations.length > 0 ? (
                  <TableContainer component={Paper} sx={{ backgroundColor: 'transparent' }}>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Resource</TableCell>
                          <TableCell>Policy</TableCell>
                          <TableCell>Violation</TableCell>
                          <TableCell align="center">Severity</TableCell>
                          <TableCell>Team</TableCell>
                          <TableCell>Detected</TableCell>
                          <TableCell align="center">Status</TableCell>
                          <TableCell align="center">Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {policyViolations.map((violation, idx) => (
                          <TableRow key={`${violation.id}-${idx}`}>
                            <TableCell component="th" scope="row">
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{violation.resource}</Typography>
                              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{violation.resourceType}</Typography>
                            </TableCell>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <Policy sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                                <Typography variant="body2">{violation.policy}</Typography>
                              </Box>
                            </TableCell>
                            <TableCell><Typography variant="body2">{violation.violation}</Typography></TableCell>
                            <TableCell align="center">
                              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {getSeverityIcon(violation.severity)}
                                <Typography variant="body2" sx={{ ml: 1, color: getSeverityColor(violation.severity), textTransform: 'capitalize' }}>
                                  {violation.severity}
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell>
                              <Chip label={violation.team} size="small" sx={{ backgroundColor: 'rgba(33, 150, 243, 0.2)', color: '#2196f3' }} />
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2">{new Date(violation.detected).toLocaleDateString()}</Typography>
                              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{new Date(violation.detected).toLocaleTimeString()}</Typography>
                            </TableCell>
                            <TableCell align="center">
                              <Chip label={violation.status} size="small"
                                sx={{ backgroundColor: `${getStatusColor(violation.status)}20`, color: getStatusColor(violation.status), textTransform: 'capitalize' }} />
                            </TableCell>
                            <TableCell align="center">
                              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
                                <Tooltip title="View Details"><IconButton size="small"><Visibility sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                                <Tooltip title="Remediate"><IconButton size="small" sx={{ color: '#4caf50' }}><CheckCircle sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                              </Box>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                ) : (
                  <Alert severity="success">No policy violations found — all resources are compliant!</Alert>
                )
              )}

              {selectedTab === 1 && (
                taggingCompliance.length > 0 ? (
                  <TableContainer component={Paper} sx={{ backgroundColor: 'transparent' }}>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Team</TableCell>
                          <TableCell align="right">Total Resources</TableCell>
                          <TableCell align="right">Compliant</TableCell>
                          <TableCell align="right">Non-Compliant</TableCell>
                          <TableCell align="center">Compliance Rate</TableCell>
                          <TableCell align="center">Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {taggingCompliance.map((team) => (
                          <TableRow key={team.team}>
                            <TableCell component="th" scope="row">
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{team.team}</Typography>
                            </TableCell>
                            <TableCell align="right"><Typography variant="body2">{team.total}</Typography></TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600 }}>{team.compliant}</Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" sx={{ color: '#f44336', fontWeight: 600 }}>{team.total - team.compliant}</Typography>
                            </TableCell>
                            <TableCell align="center">
                              <Box sx={{ width: '100%', mr: 1 }}>
                                <LinearProgress variant="determinate" value={team.compliance}
                                  sx={{
                                    height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.1)',
                                    '& .MuiLinearProgress-bar': {
                                      backgroundColor: team.compliance > 90 ? '#4caf50' : team.compliance > 75 ? '#ff9800' : '#f44336',
                                    }
                                  }} />
                                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{team.compliance}%</Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="center">
                              <Tooltip title="View Details"><IconButton size="small"><Assessment sx={{ fontSize: 16 }} /></IconButton></Tooltip>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                ) : (
                  <Alert severity="info">No tagging data available. Resources must be tagged with required tags (Name, Environment, Owner, CostCenter, Project).</Alert>
                )
              )}

              {selectedTab === 2 && (
                <Box>
                  {policyViolations.filter(v => v.severity === 'critical' || v.severity === 'high').length > 0 ? (
                    <TableContainer component={Paper} sx={{ backgroundColor: 'transparent' }}>
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableCell>Resource</TableCell>
                            <TableCell>Finding</TableCell>
                            <TableCell align="center">Severity</TableCell>
                            <TableCell align="center">Status</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {policyViolations.filter(v => v.severity === 'critical' || v.severity === 'high').map((v, idx) => (
                            <TableRow key={`sec-${idx}`}>
                              <TableCell>
                                <Typography variant="body2" sx={{ fontWeight: 600 }}>{v.resource}</Typography>
                                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{v.resourceType}</Typography>
                              </TableCell>
                              <TableCell><Typography variant="body2">{v.violation}</Typography></TableCell>
                              <TableCell align="center">
                                {getSeverityIcon(v.severity)}
                              </TableCell>
                              <TableCell align="center">
                                <Chip label={v.status} size="small"
                                  sx={{ backgroundColor: `${getStatusColor(v.status)}20`, color: getStatusColor(v.status), textTransform: 'capitalize' }} />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Alert severity="success">
                      No critical or high-severity security findings detected. Your resources are well-secured!
                    </Alert>
                  )}
                </Box>
              )}
            </CardContent></Card>
          </motion.div>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Compliance;