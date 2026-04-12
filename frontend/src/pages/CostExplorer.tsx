import React, { useState } from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    Grid,
    Alert,
    CircularProgress,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Chip,
} from '@mui/material';
import {
    Insights as InsightsIcon,
    Refresh as RefreshIcon,
    Cloud as CloudIcon,
} from '@mui/icons-material';
import { useQuery, useQueryClient } from 'react-query';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as RechartsTooltip,
    BarChart,
    Bar,
} from 'recharts';
import { costExplorerApi } from '../services/costExplorerApi';

const AXIS_STYLE = { fontSize: 11, fill: '#90a4ae' };

const CostExplorer: React.FC = () => {
    const [days, setDays] = useState(30);
    const queryClient = useQueryClient();

    const { data, isLoading, isFetching, refetch, error } = useQuery(
        ['cost-explorer', days],
        () => costExplorerApi.getOverview(days),
        { refetchOnWindowFocus: false }
    );

    const fmt = (n: number) =>
        new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n);

    const chartData =
        data?.daily?.map((d) => ({
            ...d,
            label: d.date.slice(5),
        })) ?? [];

    return (
        <>
            <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                        <InsightsIcon sx={{ mr: 1, verticalAlign: 'bottom', color: '#29b6f6' }} />
                        AWS Cost Explorer
                    </Typography>
                    <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
                        Unblended daily costs and top services from your billing account (requires{' '}
                        <Typography component="span" variant="body2" sx={{ fontFamily: 'monospace' }}>
                            ce:GetCostAndUsage
                        </Typography>
                        ).
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel id="ce-days-label">Range</InputLabel>
                        <Select
                            labelId="ce-days-label"
                            label="Range"
                            value={days}
                            onChange={(e) => setDays(Number(e.target.value))}
                        >
                            <MenuItem value={7}>Last 7 days</MenuItem>
                            <MenuItem value={30}>Last 30 days</MenuItem>
                            <MenuItem value={90}>Last 90 days</MenuItem>
                        </Select>
                    </FormControl>
                    <Button
                        startIcon={<RefreshIcon />}
                        variant="outlined"
                        onClick={() => {
                            queryClient.invalidateQueries(['cost-explorer', days]);
                            refetch();
                        }}
                        disabled={isFetching}
                    >
                        Refresh
                    </Button>
                </Box>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    Failed to load Cost Explorer data.
                </Alert>
            )}

            {data?.error && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    {data.error}
                </Alert>
            )}

            {isLoading ? (
                <Box sx={{ textAlign: 'center', py: 10 }}>
                    <CircularProgress />
                </Box>
            ) : (
                <>
                    <Grid container spacing={3} sx={{ mb: 3 }}>
                        <Grid item xs={12} md={4}>
                            <Card sx={{ background: 'linear-gradient(135deg, #01579b 0%, #0277bd 100%)' }}>
                                <CardContent>
                                    <Typography variant="caption" color="text.secondary">
                                        Total ({days} days)
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                                        {fmt(data?.total_cost_usd ?? 0)}
                                    </Typography>
                                    {data?.period_start && data?.period_end && (
                                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                            {data.period_start} → {data.period_end}
                                        </Typography>
                                    )}
                                    {data?.credential_source && (
                                        <Chip
                                            size="small"
                                            label={`Creds: ${data.credential_source}`}
                                            sx={{ mt: 1 }}
                                            variant="outlined"
                                        />
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                        <Grid item xs={12} md={8}>
                            <Card sx={{ height: '100%' }}>
                                <CardContent>
                                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                        Daily spend
                                    </Typography>
                                    {chartData.length === 0 ? (
                                        <Typography color="text.secondary">No data points in this range.</Typography>
                                    ) : (
                                        <Box sx={{ width: '100%', height: 220 }}>
                                            <ResponsiveContainer>
                                                <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                                    <XAxis dataKey="label" tick={AXIS_STYLE} />
                                                    <YAxis tick={AXIS_STYLE} tickFormatter={(v) => `$${v}`} width={56} />
                                                    <RechartsTooltip
                                                        contentStyle={{
                                                            background: '#1a1d3a',
                                                            border: '1px solid rgba(255,255,255,0.12)',
                                                            borderRadius: 8,
                                                        }}
                                                        formatter={(value: number) => [fmt(value), 'Spend']}
                                                    />
                                                    <Line
                                                        type="monotone"
                                                        dataKey="amount_usd"
                                                        stroke="#29b6f6"
                                                        strokeWidth={2}
                                                        dot={{ r: 2 }}
                                                    />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </Box>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>

                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <CloudIcon sx={{ color: '#7c4dff' }} />
                                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                    Top services
                                </Typography>
                            </Box>
                            {(!data?.by_service || data.by_service.length === 0) ? (
                                <Typography color="text.secondary">No service breakdown available.</Typography>
                            ) : (
                                <TableContainer component={Paper} sx={{ background: 'transparent' }}>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Service</TableCell>
                                                <TableCell align="right">Amount (USD)</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {data.by_service.map((row) => (
                                                <TableRow key={row.service} hover>
                                                    <TableCell>
                                                        <Typography variant="body2">{row.service}</Typography>
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                                            {fmt(row.amount_usd)}
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            )}

                            {data?.by_service && data.by_service.length > 0 && (
                                <Box sx={{ width: '100%', height: 280, mt: 3 }}>
                                    <ResponsiveContainer>
                                        <BarChart
                                            data={data.by_service.slice(0, 12)}
                                            layout="vertical"
                                            margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                            <XAxis type="number" tick={AXIS_STYLE} tickFormatter={(v) => `$${v}`} />
                                            <YAxis
                                                type="category"
                                                dataKey="service"
                                                width={180}
                                                tick={{ ...AXIS_STYLE, fontSize: 10 }}
                                            />
                                            <RechartsTooltip
                                                contentStyle={{
                                                    background: '#1a1d3a',
                                                    border: '1px solid rgba(255,255,255,0.12)',
                                                    borderRadius: 8,
                                                }}
                                                formatter={(value: number) => [fmt(value), 'Amount']}
                                            />
                                            <Bar dataKey="amount_usd" fill="#7c4dff" radius={[0, 4, 4, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </Box>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </>
    );
};

export default CostExplorer;
