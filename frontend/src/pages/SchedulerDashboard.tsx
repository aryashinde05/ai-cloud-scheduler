import React, { useState } from 'react';
import {
    Box,
    Typography,
    Grid,
    Card,
    CardContent,
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
    Tabs,
    Tab,
    Switch,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    CircularProgress,
    Tooltip,
    LinearProgress,
    Alert,
    TextField,
    FormControlLabel,
    Divider,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
} from '@mui/material';
import {
    Schedule as ScheduleIcon,
    PlayArrow as StartIcon,
    Stop as StopIcon,
    Delete as DeleteIcon,
    Analytics as AnalyzeIcon,
    Savings as SavingsIcon,
    Speed as SpeedIcon,
    CloudDone as CloudIcon,
    TrendingDown as TrendingDownIcon,
    AutoMode as AutoIcon,
    AccessTime as TimeIcon,
    CheckCircle as SuccessIcon,
    Error as ErrorIcon,
    Add as AddIcon,
    Refresh as RefreshIcon,
    SmartToy as AIIcon,
    History as HistoryIcon,
    Storage as DatabaseIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import {
    schedulerApi,
    SchedulableResource,
    ResourceAnalysis,
    Schedule,
} from '../services/schedulerApi';

// ── Tab Panel ──────────────────────────────────────────────
interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
    return (
        <div role="tabpanel" hidden={value !== index}>
            {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
        </div>
    );
}

function resourceHasSchedule(instanceId: string, schedules: Schedule[]): boolean {
    return schedules.some(
        (s) =>
            s.instance_id === instanceId ||
            (Array.isArray(s.instance_ids) && s.instance_ids.includes(instanceId))
    );
}

function scheduleHintForResource(instanceId: string, schedules: Schedule[]): string | null {
    const s = schedules.find(
        (x) =>
            x.instance_id === instanceId ||
            (Array.isArray(x.instance_ids) && x.instance_ids.includes(instanceId))
    );
    if (!s || !s.enabled) return null;
    const tz = s.timezone || 'UTC';
    return `Next cycle: stop ${s.stop_time} · start ${s.start_time} (${tz})`;
}

// ── Mini sparkline component (pure CSS) ────────────────────
function CpuSparkline({ data }: { data: Array<{ cpu: number }> }) {
    if (!data || data.length === 0) {
        return <Typography variant="caption" color="text.secondary">No data</Typography>;
    }
    const max = Math.max(...data.map((d) => d.cpu), 1);
    return (
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: '1px', height: 28 }}>
            {data.slice(-28).map((d, i) => (
                <Tooltip key={i} title={`${d.cpu}%`} arrow>
                    <Box
                        sx={{
                            width: 4,
                            height: `${Math.max((d.cpu / max) * 28, 2)}px`,
                            borderRadius: '1px',
                            background:
                                d.cpu > 50
                                    ? '#4caf50'
                                    : d.cpu > 15
                                        ? '#ff9800'
                                        : '#f44336',
                            transition: 'height 0.2s',
                        }}
                    />
                </Tooltip>
            ))}
        </Box>
    );
}

// ── Hourly usage bar chart ─────────────────────────────────
function HourlyChart({ profile }: { profile: Array<{ hour: number; label: string; avg_cpu: number }> }) {
    if (!profile || profile.length === 0) return null;
    const max = Math.max(...profile.map((p) => p.avg_cpu), 1);
    return (
        <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
                Average CPU by Hour of Day (7-day average)
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: 120, mt: 1 }}>
                {profile.map((p) => (
                    <Tooltip key={p.hour} title={`${p.label}: ${p.avg_cpu}% avg CPU`} arrow>
                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
                            <Box
                                sx={{
                                    width: '100%',
                                    height: `${Math.max((p.avg_cpu / max) * 100, 2)}px`,
                                    borderRadius: '2px 2px 0 0',
                                    background:
                                        p.avg_cpu > 50
                                            ? 'linear-gradient(180deg, #66bb6a, #43a047)'
                                            : p.avg_cpu > 15
                                                ? 'linear-gradient(180deg, #ffa726, #ef6c00)'
                                                : 'linear-gradient(180deg, #ef5350, #c62828)',
                                    transition: 'height 0.3s',
                                }}
                            />
                            {p.hour % 3 === 0 && (
                                <Typography variant="caption" sx={{ fontSize: 9, mt: 0.5, color: 'text.secondary' }}>
                                    {p.label}
                                </Typography>
                            )}
                        </Box>
                    </Tooltip>
                ))}
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#f44336' }} />
                    <Typography variant="caption" color="text.secondary">Idle (&lt;5%)</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#ff9800' }} />
                    <Typography variant="caption" color="text.secondary">Low (5–50%)</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: '#4caf50' }} />
                    <Typography variant="caption" color="text.secondary">Active (&gt;50%)</Typography>
                </Box>
            </Box>
        </Box>
    );
}

// ═══════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════
const SchedulerDashboard: React.FC = () => {
    const [tabValue, setTabValue] = useState(0);
    const [analysisDialogOpen, setAnalysisDialogOpen] = useState(false);
    const [selectedResource, setSelectedResource] = useState<SchedulableResource | null>(null);
    const [analysisResult, setAnalysisResult] = useState<ResourceAnalysis | null>(null);
    const [analysisLoading, setAnalysisLoading] = useState(false);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [scheduleForm, setScheduleForm] = useState({
        instance_id: '',
        instance_name: '',
        stop_time: '20:00',
        start_time: '08:00',
        timezone: 'UTC',
        days_pattern: 'weekdays' as 'all' | 'weekdays' | 'weekends',
        estimated_monthly_savings: 0,
        estimated_hourly_usd: '' as string | number,
    });

    const queryClient = useQueryClient();

    // ── Queries ──
    const { data: resourcesData, isLoading: resourcesLoading } = useQuery(
        'scheduler-resources',
        schedulerApi.getResources,
        { refetchInterval: 60000 }
    );
    const resources = resourcesData?.resources ?? [];
    const resourcesBanner = resourcesData?.message;

    const { data: schedules = [], isLoading: schedulesLoading } = useQuery(
        'scheduler-schedules',
        schedulerApi.getSchedules,
        { refetchInterval: 30000 }
    );

    const { data: savings } = useQuery(
        'scheduler-savings',
        schedulerApi.getSavings,
        { refetchInterval: 30000 }
    );

    const { data: history = [] } = useQuery(
        'action-history',
        schedulerApi.getActionHistory,
        { refetchInterval: 10000 }
    );

    const { data: schedSettings } = useQuery(
        'scheduler-settings',
        schedulerApi.getSchedulerSettings,
        { refetchInterval: 30000 }
    );

    const { data: smartRecs } = useQuery(
        'scheduler-smart-recs',
        schedulerApi.getSmartRecommendations,
        { refetchInterval: 120000 }
    );

    // ── Mutations ──
    const toggleSchedulerExecMutation = useMutation(
        (enabled: boolean) => schedulerApi.updateSchedulerSettings(enabled),
        {
            onSuccess: (d) => {
                toast.success(d.execution_enabled ? 'Scheduler execution enabled (cron will run)' : 'Scheduler execution paused (recommendations only)');
                queryClient.invalidateQueries('scheduler-settings');
            },
            onError: () => { toast.error('Failed to update scheduler settings'); },
        }
    );

    const createScheduleMutation = useMutation(
        (payload: {
            instance_id: string;
            instance_name?: string;
            start_time: string;
            stop_time: string;
            timezone: string;
            days_pattern: 'all' | 'weekdays' | 'weekends';
            estimated_hourly_usd?: number;
        }) =>
            schedulerApi.createProductionSchedule({
                instance_id: payload.instance_id,
                start_time: payload.start_time,
                stop_time: payload.stop_time,
                timezone: payload.timezone,
                days_pattern: payload.days_pattern,
                enabled: true,
                estimated_hourly_usd:
                    payload.estimated_hourly_usd != null && payload.estimated_hourly_usd > 0
                        ? payload.estimated_hourly_usd
                        : undefined,
            }),
        {
            onSuccess: () => {
                toast.success('Schedule created — APScheduler will start/stop instances on your times.');
                queryClient.invalidateQueries('scheduler-schedules');
                queryClient.invalidateQueries('scheduler-savings');
                setCreateDialogOpen(false);
            },
            onError: () => { toast.error('Failed to create schedule'); },
        }
    );

    const toggleScheduleMutation = useMutation(
        ({ id, enabled }: { id: string; enabled: boolean }) =>
            schedulerApi.updateSchedule(id, { enabled } as Partial<Schedule>),
        {
            onSuccess: () => {
                queryClient.invalidateQueries('scheduler-schedules');
                queryClient.invalidateQueries('scheduler-savings');
            },
        }
    );

    const deleteScheduleMutation = useMutation(
        (id: string) => schedulerApi.deleteSchedule(id),
        {
            onSuccess: () => {
                toast.success('Schedule deleted');
                queryClient.invalidateQueries('scheduler-schedules');
                queryClient.invalidateQueries('scheduler-savings');
            },
        }
    );

    const executeActionMutation = useMutation(
        ({ actionType, resourceId }: { actionType: string; resourceId: string }) =>
            schedulerApi.executeAction(actionType, resourceId),
        {
            onSuccess: (data) => {
                if (data.status === 'success') {
                    toast.success(data.message);
                } else {
                    toast.error(data.message);
                }
                queryClient.invalidateQueries('scheduler-resources');
                queryClient.invalidateQueries('action-history');
                queryClient.invalidateQueries('scheduler-savings');
            },
            onError: () => { toast.error('Action failed'); },
        }
    );

    // ── Handlers ──
    const handleAnalyze = async (resource: SchedulableResource) => {
        setSelectedResource(resource);
        setAnalysisDialogOpen(true);
        setAnalysisLoading(true);
        setAnalysisResult(null);
        try {
            const result = await schedulerApi.analyzeResource(resource.instance_id);
            setAnalysisResult(result);
        } catch {
            toast.error('Failed to analyze resource');
        } finally {
            setAnalysisLoading(false);
        }
    };

    const handleApplySuggestedSchedule = () => {
        if (!analysisResult?.suggested_schedule || !selectedResource) return;
        const sched = analysisResult.suggested_schedule;
        const hr =
            selectedResource.hourly_cost > 0
                ? selectedResource.hourly_cost
                : selectedResource.estimated_hourly_cost && selectedResource.estimated_hourly_cost > 0
                    ? selectedResource.estimated_hourly_cost
                    : undefined;
        createScheduleMutation.mutate({
            instance_id: selectedResource.instance_id,
            instance_name: selectedResource.name,
            start_time: sched.start_time.length <= 5 ? sched.start_time : sched.start_time.slice(0, 5),
            stop_time: sched.stop_time.length <= 5 ? sched.stop_time : sched.stop_time.slice(0, 5),
            timezone: 'UTC',
            days_pattern: 'weekdays',
            estimated_hourly_usd: hr,
        });
        setAnalysisDialogOpen(false);
    };

    const handleCreateSchedule = () => {
        const raw = scheduleForm.estimated_hourly_usd;
        const hourly =
            raw === '' || raw === undefined
                ? undefined
                : typeof raw === 'number'
                    ? raw
                    : parseFloat(String(raw));
        createScheduleMutation.mutate({
            instance_id: scheduleForm.instance_id,
            instance_name: scheduleForm.instance_name,
            start_time: scheduleForm.start_time,
            stop_time: scheduleForm.stop_time,
            timezone: scheduleForm.timezone,
            days_pattern: scheduleForm.days_pattern,
            estimated_hourly_usd:
                hourly !== undefined && !Number.isNaN(hourly) && hourly > 0 ? hourly : undefined,
        });
    };

    const openCreateDialog = (resource?: SchedulableResource) => {
        if (resource) {
            const hr =
                resource.hourly_cost > 0
                    ? resource.hourly_cost
                    : resource.estimated_hourly_cost && resource.estimated_hourly_cost > 0
                        ? resource.estimated_hourly_cost
                        : '';
            setScheduleForm((prev) => ({
                ...prev,
                instance_id: resource.instance_id,
                instance_name: resource.name,
                estimated_monthly_savings: Math.round(resource.monthly_cost * 0.4 * 100) / 100,
                estimated_hourly_usd: hr === '' ? '' : Math.round(hr * 10000) / 10000,
            }));
        }
        setCreateDialogOpen(true);
    };

    const formatCurrency = (n: number) =>
        new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

    const dayLabels: Record<string, string> = {
        mon: 'M', tue: 'T', wed: 'W', thu: 'T', fri: 'F', sat: 'S', sun: 'S',
    };

    // ═══════════════════════════════════════════════════════════
    // Render
    // ═══════════════════════════════════════════════════════════
    return (
        <Box>
            {/* Page Header */}
            <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                        <AIIcon sx={{ mr: 1, verticalAlign: 'bottom', color: '#7c4dff' }} />
                        Smart Scheduler
                    </Typography>
                    <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
                        AI-powered resource scheduling — analyze usage patterns, auto-schedule start/stop, save money
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1.5 }}>
                        <Chip
                            size="small"
                            label={schedSettings?.execution_enabled ? 'Execution: ON' : 'Execution: OFF'}
                            color={schedSettings?.execution_enabled ? 'success' : 'default'}
                            variant="outlined"
                        />
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={!!schedSettings?.execution_enabled}
                                    onChange={(_, v) => toggleSchedulerExecMutation.mutate(v)}
                                    disabled={toggleSchedulerExecMutation.isLoading || schedSettings === undefined}
                                    color="success"
                                />
                            }
                            label="Automated start/stop"
                        />
                    </Box>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => openCreateDialog()}
                    sx={{
                        background: 'linear-gradient(135deg, #7c4dff 0%, #536dfe 100%)',
                        '&:hover': { background: 'linear-gradient(135deg, #651fff 0%, #304ffe 100%)' },
                    }}
                >
                    New Schedule
                </Button>
            </Box>

            {resourcesBanner && (
                <Alert severity="warning" sx={{ mb: 2 }}>{resourcesBanner}</Alert>
            )}

            {smartRecs?.recommendations && smartRecs.recommendations.length > 0 && (
                <Alert severity="info" sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Cost-aware suggestions</Typography>
                    {smartRecs.recommendations.slice(0, 5).map((r) => (
                        <Typography key={r.instance_id} variant="body2">
                            {r.name} ({r.instance_id}): {r.reason}. Suggested stop {r.suggested_stop_time}, start {r.suggested_start_time} ({r.days_pattern}).
                        </Typography>
                    ))}
                </Alert>
            )}

            {/* Summary Cards */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ background: 'linear-gradient(135deg, #1a237e 0%, #283593 100%)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Active Schedules</Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                                        {savings?.active_schedules ?? 0}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        of {savings?.total_schedules ?? 0} total
                                    </Typography>
                                </Box>
                                <ScheduleIcon sx={{ fontSize: 48, color: 'rgba(124,77,255,0.4)' }} />
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ background: 'linear-gradient(135deg, #004d40 0%, #00695c 100%)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Est. Monthly Savings</Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, color: '#69f0ae' }}>
                                        {formatCurrency(savings?.estimated_monthly_savings ?? 0)}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {formatCurrency(savings?.estimated_annual_savings ?? 0)}/yr
                                    </Typography>
                                </Box>
                                <SavingsIcon sx={{ fontSize: 48, color: 'rgba(105,240,174,0.3)' }} />
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ background: 'linear-gradient(135deg, #3e2723 0%, #4e342e 100%)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Realized (logged)</Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, color: '#ffcc80' }}>
                                        {formatCurrency(
                                            savings?.realized_savings_logged_usd ?? savings?.total_realized_savings ?? 0
                                        )}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Est. $ from successful stops · {resources.length} EC2 in list
                                    </Typography>
                                </Box>
                                <CloudIcon sx={{ fontSize: 48, color: 'rgba(255,183,77,0.3)' }} />
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card sx={{ background: 'linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Actions Executed</Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                                        {savings?.actions_executed ?? 0}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {savings?.success_rate ?? 0}% success rate
                                    </Typography>
                                </Box>
                                <AutoIcon sx={{ fontSize: 48, color: 'rgba(76,175,80,0.3)' }} />
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Tabs */}
            <Tabs
                value={tabValue}
                onChange={(_e, v) => setTabValue(v)}
                sx={{
                    '& .MuiTab-root': { textTransform: 'none', fontWeight: 600 },
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                }}
            >
                <Tab icon={<SpeedIcon />} iconPosition="start" label="Resources" />
                <Tab icon={<ScheduleIcon />} iconPosition="start" label="Schedules" />
                <Tab icon={<HistoryIcon />} iconPosition="start" label="Action History" />
            </Tabs>

            {/* ── Tab 0: Resources ────────────────────────────── */}
            <TabPanel value={tabValue} index={0}>
                {resourcesLoading ? (
                    <Box sx={{ textAlign: 'center', py: 6 }}><CircularProgress /></Box>
                ) : resources.length === 0 ? (
                    <Alert severity="info" sx={{ mt: 2 }}>
                        No EC2 instances found. Connect your AWS account and make sure you have running instances.
                    </Alert>
                ) : (
                    <TableContainer component={Paper} sx={{ background: 'transparent' }}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Resource</TableCell>
                                    <TableCell>Service</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell>State</TableCell>
                                    <TableCell>AZ</TableCell>
                                    <TableCell align="center">Usage/CPU (24h)</TableCell>
                                    <TableCell align="center">Usage (7d)</TableCell>
                                    <TableCell align="right">Monthly Cost</TableCell>
                                    <TableCell align="center">Schedule</TableCell>
                                    <TableCell align="center">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {resources.map((r) => (
                                    <TableRow key={r.instance_id} hover>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.name}</Typography>
                                            <Typography variant="caption" color="text.secondary">{r.instance_id}</Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                icon={r.resource_type === 'rds' ? <DatabaseIcon fontSize="small" /> : <CloudIcon fontSize="small" />}
                                                label={r.resource_type === 'rds' ? 'RDS DB' : 'EC2'}
                                                size="small"
                                                sx={{ bgcolor: r.resource_type === 'rds' ? 'rgba(33, 150, 243, 0.1)' : 'rgba(255, 150, 0, 0.1)' }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Chip label={r.instance_type} size="small" variant="outlined" />
                                        </TableCell>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
                                                <Chip
                                                    label={r.state === 'running' ? 'Running' : r.state === 'stopped' ? 'Stopped' : r.state}
                                                    size="small"
                                                    color={r.state === 'running' || r.state === 'available' ? 'success' : r.state === 'stopped' ? 'default' : 'warning'}
                                                />
                                                {r.resource_type === 'ec2' && r.do_not_schedule && (
                                                    <Chip label="No schedule" size="small" variant="outlined" color="warning" />
                                                )}
                                                {r.resource_type === 'ec2' && r.cost_stop_suggested && (
                                                    <Chip label="High $ / idle" size="small" sx={{ bgcolor: 'rgba(255,152,0,0.2)', color: '#ff9800' }} />
                                                )}
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2">{r.az}</Typography>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
                                                <CircularProgress
                                                    variant="determinate"
                                                    value={Math.min(r.avg_cpu_24h, 100)}
                                                    size={32}
                                                    thickness={4}
                                                    sx={{
                                                        color: r.avg_cpu_24h > 50 ? '#4caf50' : r.avg_cpu_24h > 15 ? '#ff9800' : '#f44336',
                                                    }}
                                                />
                                                <Typography variant="body2">{r.avg_cpu_24h}%</Typography>
                                            </Box>
                                        </TableCell>
                                        <TableCell align="center">
                                            <CpuSparkline data={r.cpu_sparkline} />
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                                {formatCurrency(r.monthly_cost)}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
                                                {resourceHasSchedule(r.instance_id, schedules) || r.schedule_id ? (
                                                    <Chip label="Scheduled" size="small" color="primary" icon={<ScheduleIcon />} />
                                                ) : (
                                                    <Chip label="None" size="small" variant="outlined" />
                                                )}
                                                {scheduleHintForResource(r.instance_id, schedules) && (
                                                    <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center', maxWidth: 160 }}>
                                                        {scheduleHintForResource(r.instance_id, schedules)}
                                                    </Typography>
                                                )}
                                            </Box>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                                                <Tooltip title="AI Analysis">
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => handleAnalyze(r)}
                                                        sx={{ color: '#7c4dff' }}
                                                    >
                                                        <AnalyzeIcon />
                                                    </IconButton>
                                                </Tooltip>
                                                {r.state === 'running' || r.state === 'available' ? (
                                                    <Tooltip title={r.resource_type === 'rds' ? 'Stop Database' : 'Stop Instance'}>
                                                        <IconButton
                                                            size="small"
                                                            color="warning"
                                                            onClick={() =>
                                                                executeActionMutation.mutate({ actionType: 'stop', resourceId: r.instance_id })
                                                            }
                                                        >
                                                            <StopIcon />
                                                        </IconButton>
                                                    </Tooltip>
                                                ) : (
                                                    <Tooltip title={r.resource_type === 'rds' ? 'Start Database' : 'Start Instance'}>
                                                        <IconButton
                                                            size="small"
                                                            color="success"
                                                            onClick={() =>
                                                                executeActionMutation.mutate({ actionType: 'start', resourceId: r.instance_id })
                                                            }
                                                        >
                                                            <StartIcon />
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
                                                <Tooltip title="Create Schedule">
                                                    <IconButton size="small" onClick={() => openCreateDialog(r)}>
                                                        <AddIcon />
                                                    </IconButton>
                                                </Tooltip>
                                            </Box>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* ── Tab 1: Schedules ────────────────────────────── */}
            <TabPanel value={tabValue} index={1}>
                {schedulesLoading ? (
                    <Box sx={{ textAlign: 'center', py: 6 }}><CircularProgress /></Box>
                ) : schedules.length === 0 ? (
                    <Alert severity="info">
                        No schedules yet. Analyze a resource to get AI-suggested schedules, or create one manually.
                    </Alert>
                ) : (
                    <TableContainer component={Paper} sx={{ background: 'transparent' }}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Resource</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell align="center">Stop at</TableCell>
                                    <TableCell align="center">Start at</TableCell>
                                    <TableCell align="center">Days</TableCell>
                                    <TableCell align="right">Est. Savings</TableCell>
                                    <TableCell align="center">Enabled</TableCell>
                                    <TableCell align="center">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {schedules.map((s) => (
                                    <TableRow key={s.id} hover sx={{ opacity: s.enabled ? 1 : 0.5 }}>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{s.instance_name}</Typography>
                                            <Typography variant="caption" color="text.secondary">{s.instance_id}</Typography>
                                            {s.instance_ids && s.instance_ids.length > 1 && (
                                                <Typography variant="caption" display="block" color="text.secondary">
                                                    +{s.instance_ids.length - 1} more instance(s)
                                                </Typography>
                                            )}
                                            {s.timezone && (
                                                <Typography variant="caption" display="block" color="text.secondary">TZ: {s.timezone}</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={
                                                    s.schedule_type === 'production'
                                                        ? 'Cron (DB)'
                                                        : s.schedule_type === 'ai_suggested'
                                                            ? 'AI'
                                                            : 'Manual'
                                                }
                                                size="small"
                                                icon={
                                                    s.schedule_type === 'ai_suggested'
                                                        ? <AIIcon />
                                                        : <ScheduleIcon />
                                                }
                                                sx={{
                                                    bgcolor:
                                                        s.schedule_type === 'production'
                                                            ? 'rgba(33,150,243,0.2)'
                                                            : s.schedule_type === 'ai_suggested'
                                                                ? 'rgba(124,77,255,0.2)'
                                                                : 'rgba(255,255,255,0.1)',
                                                    color:
                                                        s.schedule_type === 'production'
                                                            ? '#64b5f6'
                                                            : s.schedule_type === 'ai_suggested'
                                                                ? '#b388ff'
                                                                : 'text.primary',
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell align="center">
                                            <Chip
                                                icon={<StopIcon />}
                                                label={s.stop_time}
                                                size="small"
                                                sx={{ bgcolor: 'rgba(244,67,54,0.15)', color: '#ef5350' }}
                                            />
                                        </TableCell>
                                        <TableCell align="center">
                                            <Chip
                                                icon={<StartIcon />}
                                                label={s.start_time}
                                                size="small"
                                                sx={{ bgcolor: 'rgba(76,175,80,0.15)', color: '#66bb6a' }}
                                            />
                                        </TableCell>
                                        <TableCell align="center">
                                            <Box sx={{ display: 'flex', gap: 0.3, justifyContent: 'center' }}>
                                                {['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((d) => (
                                                    <Box
                                                        key={d}
                                                        sx={{
                                                            width: 22,
                                                            height: 22,
                                                            borderRadius: '50%',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            fontSize: 10,
                                                            fontWeight: 700,
                                                            bgcolor: (s.days || []).includes(d)
                                                                ? 'primary.main'
                                                                : 'rgba(255,255,255,0.05)',
                                                            color: (s.days || []).includes(d) ? '#fff' : 'text.secondary',
                                                        }}
                                                    >
                                                        {dayLabels[d]}
                                                    </Box>
                                                ))}
                                            </Box>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Typography variant="body2" sx={{ fontWeight: 700, color: '#69f0ae' }}>
                                                {formatCurrency(s.estimated_monthly_savings)}/mo
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="center">
                                            <Switch
                                                checked={s.enabled}
                                                size="small"
                                                onChange={(e) =>
                                                    toggleScheduleMutation.mutate({ id: s.id, enabled: e.target.checked })
                                                }
                                            />
                                        </TableCell>
                                        <TableCell align="center">
                                            <Tooltip title="Delete Schedule">
                                                <IconButton
                                                    size="small"
                                                    color="error"
                                                    onClick={() => deleteScheduleMutation.mutate(s.id)}
                                                >
                                                    <DeleteIcon />
                                                </IconButton>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* ── Tab 2: Action History ───────────────────────── */}
            <TabPanel value={tabValue} index={2}>
                {history.length === 0 ? (
                    <Alert severity="info">
                        No actions executed yet. Use the Resources tab to start/stop instances or apply schedules.
                    </Alert>
                ) : (
                    <TableContainer component={Paper} sx={{ background: 'transparent' }}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Time</TableCell>
                                    <TableCell>Resource</TableCell>
                                    <TableCell>Action</TableCell>
                                    <TableCell>Status</TableCell>
                                    <TableCell align="right">Est. savings</TableCell>
                                    <TableCell>Message</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {history.map((h) => (
                                    <TableRow key={h.id} hover>
                                        <TableCell>
                                            <Typography variant="body2">
                                                {new Date(h.timestamp).toLocaleString()}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                                {h.instance_id || h.resource_id}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={h.action}
                                                size="small"
                                                icon={h.action === 'stop' ? <StopIcon /> : h.action === 'start' ? <StartIcon /> : <DeleteIcon />}
                                                variant="outlined"
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={h.status}
                                                size="small"
                                                color={h.status === 'success' ? 'success' : 'error'}
                                                icon={h.status === 'success' ? <SuccessIcon /> : <ErrorIcon />}
                                            />
                                        </TableCell>
                                        <TableCell align="right">
                                            {h.estimated_savings_usd != null && h.estimated_savings_usd > 0 ? (
                                                <Typography variant="body2" sx={{ fontFamily: 'monospace', color: '#69f0ae' }}>
                                                    {formatCurrency(h.estimated_savings_usd)}
                                                </Typography>
                                            ) : (
                                                <Typography variant="caption" color="text.secondary">—</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" color="text.secondary">
                                                {(() => {
                                                    const rid = h.resource_id || h.instance_id || '';
                                                    const ts = h.timestamp ? new Date(h.timestamp).toLocaleString() : '';
                                                    return `${h.action} ${rid} at ${ts} — ${h.status}${h.message ? ` (${h.message})` : ''}`;
                                                })()}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* ═════════════════════════════════════════════════════ */}
            {/* Analysis Dialog                                      */}
            {/* ═════════════════════════════════════════════════════ */}
            <Dialog
                open={analysisDialogOpen}
                onClose={() => setAnalysisDialogOpen(false)}
                maxWidth="md"
                fullWidth
                PaperProps={{
                    sx: {
                        background: 'linear-gradient(135deg, #1a1d3a 0%, #2a2d5a 100%)',
                        border: '1px solid rgba(124,77,255,0.3)',
                    },
                }}
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AIIcon sx={{ color: '#7c4dff' }} />
                    AI Usage Analysis — {selectedResource?.name}
                </DialogTitle>
                <DialogContent>
                    {analysisLoading ? (
                        <Box sx={{ textAlign: 'center', py: 6 }}>
                            <CircularProgress sx={{ color: '#7c4dff' }} />
                            <Typography sx={{ mt: 2 }} color="text.secondary">
                                Analyzing CloudWatch metrics for the last 7 days...
                            </Typography>
                        </Box>
                    ) : analysisResult?.analysis?.error ? (
                        <Alert severity="error" sx={{ mt: 1 }}>
                            Analysis failed: {analysisResult.analysis.error}
                        </Alert>
                    ) : analysisResult ? (
                        <Box>
                            {/* Stats row */}
                            <Grid container spacing={2} sx={{ mb: 3 }}>
                                <Grid item xs={3}>
                                    <Card sx={{ bgcolor: 'rgba(255,255,255,0.05)' }}>
                                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                            <Typography variant="caption" color="text.secondary">Avg CPU</Typography>
                                            <Typography variant="h5" sx={{ fontWeight: 700 }}>
                                                {analysisResult.analysis.avg_cpu}%
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid item xs={3}>
                                    <Card sx={{ bgcolor: 'rgba(255,255,255,0.05)' }}>
                                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                            <Typography variant="caption" color="text.secondary">Max CPU</Typography>
                                            <Typography variant="h5" sx={{ fontWeight: 700 }}>
                                                {analysisResult.analysis.max_cpu}%
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid item xs={3}>
                                    <Card sx={{ bgcolor: 'rgba(244,67,54,0.1)' }}>
                                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                            <Typography variant="caption" color="text.secondary">Idle Hours/Day</Typography>
                                            <Typography variant="h5" sx={{ fontWeight: 700, color: '#ef5350' }}>
                                                {analysisResult.analysis.idle_hours_per_day}h
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid item xs={3}>
                                    <Card sx={{ bgcolor: 'rgba(105,240,174,0.1)' }}>
                                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                            <Typography variant="caption" color="text.secondary">Potential Savings</Typography>
                                            <Typography variant="h5" sx={{ fontWeight: 700, color: '#69f0ae' }}>
                                                {formatCurrency(analysisResult.savings.estimated_monthly_savings)}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            </Grid>

                            {/* Hourly profile chart */}
                            <HourlyChart profile={analysisResult.analysis.hourly_profile} />

                            {/* Idle windows */}
                            {analysisResult.analysis.idle_windows?.length > 0 && (
                                <Box sx={{ mt: 3 }}>
                                    <Typography variant="subtitle2" gutterBottom>
                                        Detected Idle Windows
                                    </Typography>
                                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                        {analysisResult.analysis.idle_windows.map((w, i) => (
                                            <Chip
                                                key={i}
                                                icon={<TimeIcon />}
                                                label={`${w.start}–${w.end} (${w.duration_hours}h, ${w.type})`}
                                                sx={{ bgcolor: 'rgba(244,67,54,0.15)', color: '#ef5350' }}
                                            />
                                        ))}
                                    </Box>
                                </Box>
                            )}

                            {/* AI Suggested Schedule */}
                            {analysisResult.suggested_schedule && (
                                <Box
                                    sx={{
                                        mt: 3,
                                        p: 2.5,
                                        borderRadius: 2,
                                        background: 'linear-gradient(135deg, rgba(124,77,255,0.15), rgba(83,109,254,0.1))',
                                        border: '1px solid rgba(124,77,255,0.4)',
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                                        <AIIcon sx={{ color: '#b388ff' }} />
                                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#b388ff' }}>
                                            AI Recommendation
                                        </Typography>
                                        <Chip
                                            label={`${analysisResult.suggested_schedule.confidence}% confidence`}
                                            size="small"
                                            sx={{ bgcolor: 'rgba(124,77,255,0.3)', color: '#e8eaf6' }}
                                        />
                                    </Box>
                                    <Typography variant="body2" sx={{ mb: 2 }}>
                                        {analysisResult.suggested_schedule.description}
                                    </Typography>
                                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                        <Chip icon={<StopIcon />} label={`Stop: ${analysisResult.suggested_schedule.stop_time}`}
                                            sx={{ bgcolor: 'rgba(244,67,54,0.15)', color: '#ef5350' }} />
                                        <Chip icon={<StartIcon />} label={`Start: ${analysisResult.suggested_schedule.start_time}`}
                                            sx={{ bgcolor: 'rgba(76,175,80,0.15)', color: '#66bb6a' }} />
                                        <Chip icon={<SavingsIcon />}
                                            label={`Save ${formatCurrency(analysisResult.suggested_schedule.estimated_monthly_savings)}/mo`}
                                            sx={{ bgcolor: 'rgba(105,240,174,0.15)', color: '#69f0ae' }} />
                                    </Box>
                                </Box>
                            )}

                            {/* Cost breakdown */}
                            <Box sx={{ mt: 3 }}>
                                <Typography variant="subtitle2" gutterBottom>Cost Summary</Typography>
                                <Box sx={{ display: 'flex', gap: 3 }}>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Current Monthly</Typography>
                                        <Typography variant="h6">{formatCurrency(analysisResult.savings.current_monthly_cost)}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">With Scheduling</Typography>
                                        <Typography variant="h6" sx={{ color: '#69f0ae' }}>
                                            {formatCurrency(
                                                analysisResult.savings.current_monthly_cost -
                                                analysisResult.savings.estimated_monthly_savings
                                            )}
                                        </Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Savings %</Typography>
                                        <Typography variant="h6" sx={{ color: '#ffd740' }}>
                                            {analysisResult.savings.savings_percentage}%
                                        </Typography>
                                    </Box>
                                </Box>
                            </Box>
                        </Box>
                    ) : null}
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2 }}>
                    <Button onClick={() => setAnalysisDialogOpen(false)}>Close</Button>
                    {analysisResult?.suggested_schedule && (
                        <Button
                            variant="contained"
                            startIcon={<AutoIcon />}
                            onClick={handleApplySuggestedSchedule}
                            sx={{
                                background: 'linear-gradient(135deg, #7c4dff 0%, #536dfe 100%)',
                                '&:hover': { background: 'linear-gradient(135deg, #651fff 0%, #304ffe 100%)' },
                            }}
                        >
                            Apply AI Schedule
                        </Button>
                    )}
                </DialogActions>
            </Dialog>

            {/* ═════════════════════════════════════════════════════ */}
            {/* Create Schedule Dialog                               */}
            {/* ═════════════════════════════════════════════════════ */}
            <Dialog
                open={createDialogOpen}
                onClose={() => setCreateDialogOpen(false)}
                maxWidth="sm"
                fullWidth
                PaperProps={{
                    sx: {
                        background: 'linear-gradient(135deg, #1a1d3a 0%, #2a2d5a 100%)',
                        border: '1px solid rgba(255,255,255,0.15)',
                    },
                }}
            >
                <DialogTitle>
                    <ScheduleIcon sx={{ mr: 1, verticalAlign: 'bottom' }} />
                    Create Schedule
                </DialogTitle>
                <DialogContent>
                    <TextField
                        label="Instance ID"
                        fullWidth
                        margin="normal"
                        value={scheduleForm.instance_id}
                        onChange={(e) => setScheduleForm({ ...scheduleForm, instance_id: e.target.value })}
                    />
                    <TextField
                        label="Instance Name"
                        fullWidth
                        margin="normal"
                        value={scheduleForm.instance_name}
                        onChange={(e) => setScheduleForm({ ...scheduleForm, instance_name: e.target.value })}
                    />
                    <Grid container spacing={2} sx={{ mt: 0.5 }}>
                        <Grid item xs={6}>
                            <TextField
                                label="Stop Time"
                                type="time"
                                fullWidth
                                value={scheduleForm.stop_time}
                                onChange={(e) => setScheduleForm({ ...scheduleForm, stop_time: e.target.value })}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Grid>
                        <Grid item xs={6}>
                            <TextField
                                label="Start Time"
                                type="time"
                                fullWidth
                                value={scheduleForm.start_time}
                                onChange={(e) => setScheduleForm({ ...scheduleForm, start_time: e.target.value })}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Grid>
                        <Grid item xs={12}>
                            <TextField
                                label="Timezone (IANA)"
                                fullWidth
                                placeholder="UTC, Asia/Kolkata, America/New_York"
                                value={scheduleForm.timezone}
                                onChange={(e) => setScheduleForm({ ...scheduleForm, timezone: e.target.value })}
                                helperText="Cron jobs run in this timezone"
                            />
                        </Grid>
                        <Grid item xs={12}>
                            <FormControl fullWidth>
                                <InputLabel id="days-pattern-label">Schedule pattern</InputLabel>
                                <Select
                                    labelId="days-pattern-label"
                                    label="Schedule pattern"
                                    value={scheduleForm.days_pattern}
                                    onChange={(e) =>
                                        setScheduleForm({
                                            ...scheduleForm,
                                            days_pattern: e.target.value as 'all' | 'weekdays' | 'weekends',
                                        })
                                    }
                                >
                                    <MenuItem value="all">Every day</MenuItem>
                                    <MenuItem value="weekdays">Weekdays (Mon–Fri)</MenuItem>
                                    <MenuItem value="weekends">Weekends (Sat–Sun)</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid item xs={12}>
                            <TextField
                                label="Est. hourly cost (USD, optional)"
                                fullWidth
                                type="number"
                                inputProps={{ min: 0, step: 0.0001 }}
                                value={scheduleForm.estimated_hourly_usd}
                                onChange={(e) =>
                                    setScheduleForm({ ...scheduleForm, estimated_hourly_usd: e.target.value })
                                }
                                helperText="Used to estimate savings per stop; defaults on the server if empty"
                            />
                        </Grid>
                    </Grid>
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2 }}>
                    <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleCreateSchedule}
                        disabled={!scheduleForm.instance_id}
                        sx={{
                            background: 'linear-gradient(135deg, #7c4dff 0%, #536dfe 100%)',
                        }}
                    >
                        Create Schedule
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default SchedulerDashboard;
