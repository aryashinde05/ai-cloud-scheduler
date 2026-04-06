import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Chip, Alert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, LinearProgress, Tabs, Tab, IconButton, Tooltip, Button,
  Select, MenuItem, FormControl, InputLabel, CircularProgress,
} from '@mui/material';
import { Refresh, CloudOff, Computer, Storage, Memory, Language } from '@mui/icons-material';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip,
  ResponsiveContainer, LineChart, Line, ScatterChart, Scatter,
  ZAxis, Legend, Cell,
} from 'recharts';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { SkeletonLoader } from '../components/Loading';
import numeral from 'numeral';

// ── Types ────────────────────────────────────────────────────────────────────

interface EC2Instance {
  instance_id: string;
  instance_type: string;
  state: string;
  cpu_utilization: number;
  memory_utilization: number;
  network_in_mb: number;
  network_out_mb: number;
  monthly_cost: number;
  region: string;
  name?: string;
  recommendation?: string;
}

interface EBSVolume {
  volume_id: string;
  volume_type: string;
  size_gb: number;
  state: string;
  attached_instance?: string;
  read_ops: number;
  write_ops: number;
  monthly_cost: number;
}

interface RDSInstance {
  db_identifier: string;
  db_class: string;
  engine: string;
  status: string;
  cpu_utilization: number;
  connections: number;
  storage_gb: number;
  monthly_cost: number;
}

// ── Mock data (replaced by real API when backend endpoint exists) ─────────────



// ── Colour helpers ────────────────────────────────────────────────────────────

const utilizationColor = (v: number) =>
  v >= 80 ? '#f44336' : v >= 40 ? '#ff9800' : '#4caf50';

const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: '#1a1d3a',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 8,
  color: '#fff',
  fontSize: 13,
};

// ── Sub-components ────────────────────────────────────────────────────────────

const SummaryCard: React.FC<{
  title: string; value: string | number; sub: string;
  icon: React.ReactNode; color: string;
}> = ({ title, value, sub, icon, color }) => (
  <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>{title}</Typography>
            <Typography variant="h4" fontWeight={700}>{value}</Typography>
            <Typography variant="caption" color="text.secondary">{sub}</Typography>
          </Box>
          <Box sx={{ color, opacity: 0.85 }}>{icon}</Box>
        </Box>
      </CardContent>
    </Card>
  </motion.div>
);

// ── EC2 Tab ───────────────────────────────────────────────────────────────────

const EC2Tab: React.FC<{ instances: EC2Instance[] }> = ({ instances }) => {
  const cpuData = instances.map(i => ({
    name: i.name || i.instance_id.slice(-6),
    cpu: i.cpu_utilization,
    memory: i.memory_utilization,
    fill: utilizationColor(i.cpu_utilization),
  }));

  const scatterData = instances.map(i => ({
    cpu: i.cpu_utilization,
    cost: i.monthly_cost,
    name: i.name || i.instance_id.slice(-6),
  }));

  const idle = instances.filter(i => i.cpu_utilization < 5).length;
  const underused = instances.filter(i => i.cpu_utilization >= 5 && i.cpu_utilization < 20).length;

  return (
    <Box>
      {(idle > 0 || underused > 0) && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {idle} idle instance{idle !== 1 ? 's' : ''} (CPU &lt; 5%) and {underused} underutilized instance{underused !== 1 ? 's' : ''} (CPU &lt; 20%) detected — potential savings available.
        </Alert>
      )}

      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* CPU + Memory bar chart */}
        <Grid item xs={12} lg={7}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>CPU vs Memory Utilization (%)</Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={cpuData} margin={{ top: 5, right: 10, left: -10, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                  <XAxis dataKey="name" stroke="#b0bec5" angle={-35} textAnchor="end" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#b0bec5" domain={[0, 100]} tickFormatter={v => `${v}%`} />
                  <ChartTooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [`${v}%`]} />
                  <Legend />
                  <Bar dataKey="cpu" name="CPU %" radius={[4, 4, 0, 0]}>
                    {cpuData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                  <Bar dataKey="memory" name="Memory %" fill="#2196f3" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Cost vs CPU scatter */}
        <Grid item xs={12} lg={5}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Cost vs CPU Utilization</Typography>
              <Typography variant="caption" color="text.secondary">
                Dots in the bottom-right are expensive but underutilized
              </Typography>
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                  <XAxis dataKey="cpu" name="CPU %" stroke="#b0bec5" tickFormatter={v => `${v}%`} label={{ value: 'CPU %', position: 'insideBottom', offset: -2, fill: '#b0bec5', fontSize: 12 }} />
                  <YAxis dataKey="cost" name="Monthly Cost" stroke="#b0bec5" tickFormatter={v => `$${v}`} />
                  <ZAxis range={[60, 60]} />
                  <ChartTooltip
                    contentStyle={TOOLTIP_STYLE}
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ payload }: any) => {
                      if (!payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div style={TOOLTIP_STYLE}>
                          <p style={{ margin: 0, fontWeight: 600 }}>{d.name}</p>
                          <p style={{ margin: 0 }}>CPU: {d.cpu}%</p>
                          <p style={{ margin: 0 }}>Cost: ${d.cost}/mo</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter data={scatterData} fill="#ff9800" />
                </ScatterChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Instance table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Instance Details</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name / ID</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Region</TableCell>
                  <TableCell align="center">CPU %</TableCell>
                  <TableCell align="center">Mem %</TableCell>
                  <TableCell align="right">Monthly Cost</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {instances.map(inst => (
                  <TableRow key={inst.instance_id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>{inst.name || inst.instance_id}</Typography>
                      <Typography variant="caption" color="text.secondary">{inst.instance_id}</Typography>
                    </TableCell>
                    <TableCell><Typography variant="body2">{inst.instance_type}</Typography></TableCell>
                    <TableCell><Typography variant="body2">{inst.region}</Typography></TableCell>
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress variant="determinate" value={inst.cpu_utilization}
                          sx={{ flex: 1, height: 6, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.1)',
                            '& .MuiLinearProgress-bar': { bgcolor: utilizationColor(inst.cpu_utilization) } }} />
                        <Typography variant="caption" sx={{ minWidth: 30 }}>{inst.cpu_utilization}%</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress variant="determinate" value={inst.memory_utilization}
                          sx={{ flex: 1, height: 6, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.1)',
                            '& .MuiLinearProgress-bar': { bgcolor: utilizationColor(inst.memory_utilization) } }} />
                        <Typography variant="caption" sx={{ minWidth: 30 }}>{inst.memory_utilization}%</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" fontWeight={600}>${inst.monthly_cost}/mo</Typography>
                    </TableCell>
                    <TableCell>
                      {inst.recommendation
                        ? <Chip label={inst.recommendation} size="small" color="warning" sx={{ fontSize: '0.65rem' }} />
                        : <Chip label={inst.state} size="small" color={inst.state === 'running' ? 'success' : 'default'} />}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
};

// ── EBS Tab ───────────────────────────────────────────────────────────────────

const EBSTab: React.FC<{ volumes: EBSVolume[] }> = ({ volumes }) => {
  const unattached = volumes.filter(v => v.state === 'available');
  const opsData = volumes.map(v => ({
    name: v.volume_id.slice(-8),
    reads: v.read_ops,
    writes: v.write_ops,
  }));

  const typeData = Object.entries(
    volumes.reduce((acc: Record<string, number>, v) => {
      acc[v.volume_type] = (acc[v.volume_type] || 0) + v.size_gb;
      return acc;
    }, {})
  ).map(([type, gb]) => ({ type, gb }));

  return (
    <Box>
      {unattached.length > 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {unattached.length} unattached EBS volume{unattached.length !== 1 ? 's' : ''} found — these are incurring cost with no active use.
        </Alert>
      )}

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} lg={7}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Read / Write IOPS by Volume</Typography>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={opsData} margin={{ top: 5, right: 10, left: -10, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                  <XAxis dataKey="name" stroke="#b0bec5" angle={-30} textAnchor="end" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#b0bec5" />
                  <ChartTooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend />
                  <Bar dataKey="reads" name="Read IOPS" fill="#2196f3" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="writes" name="Write IOPS" fill="#ff9800" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={5}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Storage by Volume Type (GB)</Typography>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={typeData} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                  <XAxis type="number" stroke="#b0bec5" tickFormatter={v => `${v} GB`} />
                  <YAxis type="category" dataKey="type" stroke="#b0bec5" />
                  <ChartTooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [`${v} GB`]} />
                  <Bar dataKey="gb" name="Total GB" fill="#4caf50" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Volume Details</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Volume ID</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell align="right">Size</TableCell>
                  <TableCell>Attached To</TableCell>
                  <TableCell align="right">Read IOPS</TableCell>
                  <TableCell align="right">Write IOPS</TableCell>
                  <TableCell align="right">Monthly Cost</TableCell>
                  <TableCell>State</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {volumes.map(vol => (
                  <TableRow key={vol.volume_id} hover>
                    <TableCell><Typography variant="body2" fontFamily="monospace">{vol.volume_id}</Typography></TableCell>
                    <TableCell><Chip label={vol.volume_type} size="small" variant="outlined" /></TableCell>
                    <TableCell align="right"><Typography variant="body2">{vol.size_gb} GB</Typography></TableCell>
                    <TableCell>
                      <Typography variant="body2" color={vol.attached_instance ? 'text.primary' : 'warning.main'}>
                        {vol.attached_instance || 'Unattached'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right"><Typography variant="body2">{vol.read_ops}</Typography></TableCell>
                    <TableCell align="right"><Typography variant="body2">{vol.write_ops}</Typography></TableCell>
                    <TableCell align="right"><Typography variant="body2" fontWeight={600}>${vol.monthly_cost}/mo</Typography></TableCell>
                    <TableCell>
                      <Chip label={vol.state} size="small"
                        color={vol.state === 'in-use' ? 'success' : 'warning'} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
};

// ── RDS Tab ───────────────────────────────────────────────────────────────────

const RDSTab: React.FC<{ instances: RDSInstance[] }> = ({ instances }) => {
  const cpuData = instances.map(i => ({
    name: i.db_identifier,
    cpu: i.cpu_utilization,
    connections: i.connections,
    fill: utilizationColor(i.cpu_utilization),
  }));

  return (
    <Box>
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>CPU Utilization by DB Instance (%)</Typography>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={cpuData} margin={{ top: 5, right: 10, left: -10, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                  <XAxis dataKey="name" stroke="#b0bec5" angle={-25} textAnchor="end" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#b0bec5" domain={[0, 100]} tickFormatter={v => `${v}%`} />
                  <ChartTooltip contentStyle={TOOLTIP_STYLE} formatter={(v: any) => [`${v}%`]} />
                  <Bar dataKey="cpu" name="CPU %" radius={[4, 4, 0, 0]}>
                    {cpuData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Active Connections by DB Instance</Typography>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={cpuData} margin={{ top: 5, right: 10, left: -10, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                  <XAxis dataKey="name" stroke="#b0bec5" angle={-25} textAnchor="end" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#b0bec5" />
                  <ChartTooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="connections" name="Connections" fill="#9c27b0" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>RDS Instance Details</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Identifier</TableCell>
                  <TableCell>Class</TableCell>
                  <TableCell>Engine</TableCell>
                  <TableCell align="center">CPU %</TableCell>
                  <TableCell align="right">Connections</TableCell>
                  <TableCell align="right">Storage</TableCell>
                  <TableCell align="right">Monthly Cost</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {instances.map(db => (
                  <TableRow key={db.db_identifier} hover>
                    <TableCell><Typography variant="body2" fontWeight={600}>{db.db_identifier}</Typography></TableCell>
                    <TableCell><Typography variant="body2">{db.db_class}</Typography></TableCell>
                    <TableCell><Chip label={db.engine} size="small" variant="outlined" /></TableCell>
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress variant="determinate" value={db.cpu_utilization}
                          sx={{ flex: 1, height: 6, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.1)',
                            '& .MuiLinearProgress-bar': { bgcolor: utilizationColor(db.cpu_utilization) } }} />
                        <Typography variant="caption" sx={{ minWidth: 30 }}>{db.cpu_utilization}%</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right"><Typography variant="body2">{db.connections}</Typography></TableCell>
                    <TableCell align="right"><Typography variant="body2">{db.storage_gb} GB</Typography></TableCell>
                    <TableCell align="right"><Typography variant="body2" fontWeight={600}>${db.monthly_cost}/mo</Typography></TableCell>
                    <TableCell><Chip label={db.status} size="small" color="success" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────

const InfrastructureAnalysis: React.FC = () => {
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [noAws, setNoAws] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [ec2, setEc2] = useState<EC2Instance[]>([]);
  const [ebs, setEbs] = useState<EBSVolume[]>([]);
  const [rds, setRds] = useState<RDSInstance[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<string>('all');
  const [defaultRegion, setDefaultRegion] = useState<string | null>(null);
  const [availableRegions, setAvailableRegions] = useState<string[]>([]);
  const [awsError, setAwsError] = useState<string | null>(null);

  const ALL_REGIONS = [
    'us-east-1','us-east-2','us-west-1','us-west-2',
    'eu-west-1','eu-west-2','eu-central-1','eu-north-1',
    'ap-southeast-1','ap-southeast-2','ap-northeast-1','ap-northeast-2',
    'ap-south-1','sa-east-1','ca-central-1',
  ];

  const load = async (regionFilter?: string) => {
    setLoading(true);
    setNoAws(false);
    setAwsError(null);
    setIsDemo(false);

    // Step 1: check if account is stored at all
    let statusConnected = false;
    try {
      const statusRes = await api.get('/api/v1/aws/status');
      statusConnected = statusRes.data?.connected === true;
      setDefaultRegion(statusRes.data?.region ?? null);
    } catch {
      // backend unreachable
      setDefaultRegion(null);
    }

    if (!statusConnected) {
      setNoAws(true);
      setLoading(false);
      return;
    }

    // Step 2: fetch resources — scans all regions unless a filter is set
    try {
      const params = regionFilter && regionFilter !== 'all' ? `?region=${regionFilter}` : '';
      const res = await api.get(`/api/v1/aws/resources${params}`);
      const all: any[] = Array.isArray(res.data) ? res.data : [];

      // Collect unique regions from results
      const regions = Array.from(new Set(all.map((r: any) => r.region).filter(Boolean))) as string[];
      setAvailableRegions(regions);

      const ec2Instances: EC2Instance[] = all
        .filter(r => r.resource_type === 'ec2_instance')
        .map(r => ({
          instance_id: r.resource_id,
          name: r.name || r.resource_id,
          instance_type: r.instance_type || 'unknown',
          state: r.state || 'unknown',
          cpu_utilization: r.cpu_utilization ?? 0,
          memory_utilization: 0,
          network_in_mb: 0,
          network_out_mb: 0,
          monthly_cost: r.monthly_cost ?? 0,
          region: r.region || 'unknown',
          recommendation: r.is_idle
            ? 'Idle — consider stopping'
            : r.is_oversized
            ? 'Underutilized — consider downsizing'
            : undefined,
        }));

      const ebsVolumes: EBSVolume[] = all
        .filter(r => r.resource_type === 'ebs_volume')
        .map(r => ({
          volume_id: r.resource_id,
          volume_type: r.volume_type || 'gp2',
          size_gb: r.volume_size ?? 0,
          state: r.state || 'unknown',
          attached_instance: r.is_unattached ? undefined : r.resource_id,
          read_ops: 0,
          write_ops: 0,
          monthly_cost: r.monthly_cost ?? 0,
        }));

      setEc2(ec2Instances);
      setEbs(ebsVolumes);

      // Fetch real RDS instances
      try {
        const rdsRes = await api.get('/api/v1/aws/rds');
        const rdsAll: any[] = Array.isArray(rdsRes.data) ? rdsRes.data : [];
        const rdsInstances: RDSInstance[] = rdsAll.map(r => ({
          db_identifier: r.resource_id,
          db_class: r.instance_type || 'unknown',
          engine: r.engine || 'unknown',
          status: r.state || 'unknown',
          cpu_utilization: r.cpu_utilization ?? 0,
          connections: 0,
          storage_gb: r.volume_size ?? 0,
          monthly_cost: r.monthly_cost ?? 0,
        }));
        setRds(rdsInstances);
      } catch {
        setRds([]);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
      setAwsError(detail);
      try {
        const cached = await api.get('/api/v1/aws/instances');
        const all: any[] = Array.isArray(cached.data) ? cached.data : [];
        setEc2(all.filter(r => r.resource_type === 'ec2_instance').map(r => ({
          instance_id: r.resource_id, name: r.name || r.resource_id,
          instance_type: r.instance_type || 'unknown', state: r.state || 'unknown',
          cpu_utilization: r.cpu_utilization ?? 0, memory_utilization: 0,
          network_in_mb: 0, network_out_mb: 0, monthly_cost: r.monthly_cost ?? 0,
          region: r.region || 'unknown',
          recommendation: r.is_idle ? 'Idle — consider stopping' : r.is_oversized ? 'Underutilized — consider downsizing' : undefined,
        })));
        setEbs([]);
        setRds([]);
      } catch {
        setEc2([]); setEbs([]); setRds([]);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRegionChange = (region: string) => {
    setSelectedRegion(region);
    load(region);
  };

  if (loading) return <SkeletonLoader variant="dashboard" />;

  if (noAws) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <CloudOff sx={{ fontSize: 80, color: 'text.secondary', mb: 3 }} />
        <Typography variant="h4" fontWeight={700} sx={{ mb: 2 }}>No AWS Account Connected</Typography>
        <Typography color="text.secondary" sx={{ mb: 4 }}>
          Connect your AWS account to see live infrastructure analysis.
        </Typography>
        <Button variant="contained" size="large" onClick={() => navigate('/onboarding')}>
          Connect AWS Account
        </Button>
      </Box>
    );
  }

  const totalMonthlyCost = [...ec2, ...ebs, ...rds].reduce((s, r) => s + r.monthly_cost, 0);
  const idleEc2 = ec2.filter(i => i.cpu_utilization < 5).length;
  const unattachedEbs = ebs.filter(v => v.state === 'available').length;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" fontWeight={700}>Infrastructure Analysis</Typography>
          <Typography color="text.secondary" variant="body2" sx={{ mt: 0.5 }}>
            Per-instance utilization, storage I/O, and database metrics
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Region filter */}
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Region</InputLabel>
            <Select
              value={selectedRegion}
              label="Region"
              onChange={(e) => handleRegionChange(e.target.value)}
              startAdornment={<Language sx={{ mr: 1, fontSize: 18, color: 'text.secondary' }} />}
            >
              <MenuItem value="all">All Regions</MenuItem>
              {(availableRegions.length > 0 ? availableRegions : ALL_REGIONS).map(r => (
                <MenuItem key={r} value={r}>{r}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tooltip title="Refresh">
            <IconButton onClick={() => load(selectedRegion)} sx={{ bgcolor: 'rgba(33,150,243,0.1)' }}>
              {loading ? <CircularProgress size={20} /> : <Refresh />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Banners */}
      {awsError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          AWS refresh failed: {awsError}. Showing cached data if available.
        </Alert>
      )}
      {!awsError && isDemo && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Demo data — backend is unreachable. Connect your AWS account and ensure the backend is running.
        </Alert>
      )}
      {!awsError && !isDemo && (
        <Alert severity="success" sx={{ mb: 3 }}>
          {selectedRegion === 'all'
            ? `Showing resources in default region${defaultRegion ? ` (${defaultRegion})` : ''}. Found: ${availableRegions.join(', ') || 'none yet'}.`
            : `Showing resources in ${selectedRegion}.`}
        </Alert>
      )}
      {ec2.length === 0 && ebs.length === 0 && !awsError && !loading && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          No resources found. The scan covers the default region automatically — if you still see nothing, check that your IAM credentials have <strong>ec2:DescribeInstances</strong> permission.
        </Alert>
      )}

      {/* Summary cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <SummaryCard title="EC2 Instances" value={ec2.length} sub={`${ec2.filter(i => i.state === 'running').length} running`}
            icon={<Computer sx={{ fontSize: 40 }} />} color="#ff9800" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <SummaryCard title="EBS Volumes" value={ebs.length} sub={`${unattachedEbs} unattached`}
            icon={<Storage sx={{ fontSize: 40 }} />} color="#2196f3" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <SummaryCard title="RDS Instances" value={rds.length} sub="databases"
            icon={<Memory sx={{ fontSize: 40 }} />} color="#9c27b0" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <SummaryCard title="Total Monthly Cost" value={numeral(totalMonthlyCost).format('$0,0')}
            sub={`${idleEc2} idle EC2 instances`}
            icon={<Computer sx={{ fontSize: 40 }} />} color="#4caf50" />
        </Grid>
      </Grid>

      {/* Tabs */}
      <Card>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: '1px solid rgba(255,255,255,0.1)', px: 2 }}>
          <Tab label={`EC2 Instances (${ec2.length})`} />
          <Tab label={`EBS Volumes (${ebs.length})`} />
          <Tab label={`RDS Instances (${rds.length})`} />
        </Tabs>
        <CardContent>
          {tab === 0 && <EC2Tab instances={ec2} />}
          {tab === 1 && <EBSTab volumes={ebs} />}
          {tab === 2 && <RDSTab instances={rds} />}
        </CardContent>
      </Card>
    </Box>
  );
};

export default InfrastructureAnalysis;
