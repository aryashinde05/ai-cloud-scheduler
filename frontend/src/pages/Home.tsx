import React from 'react';
import {
    Box,
    Container,
    Typography,
    Grid,
    Card,
    CardContent,
    Button,
    useTheme,
    alpha
} from '@mui/material';
import {
    CloudQueue,
    Moving,
    ArrowForward,
    AutoGraph,
    Storage
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Home: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const { isAuthenticated, loading } = useAuth();

    // Redirect logged-in users straight to the dashboard
    if (!loading && isAuthenticated) {
        return <Navigate to="/dashboard" replace />;
    }

    const menuItems = [
        {
            title: 'Cloud Intelligence Dashboard',
            description: 'Connect AWS or Azure and get real-time cost analysis, automated scheduling, and resource optimization.',
            icon: <AutoGraph sx={{ fontSize: 48 }} />,
            path: '/dashboard',
            color: theme.palette.primary.main,
            features: ['AWS Cost Optimization', 'Azure Cost Control', 'Resource Scheduling']
        },
        {
            title: 'Global Migration Planner',
            description: 'Plan your journey from local storage to the cloud. Analyze TCO, risks, and timelines without an AWS account.',
            icon: <Moving sx={{ fontSize: 48 }} />,
            path: '/migration-wizard',
            color: theme.palette.warning.main,
            features: ['On-Prem to AWS', 'TCO Analysis', 'Risk Assessment']
        }
    ];

    return (
        <Box
            sx={{
                minHeight: '100vh',
                background: `radial-gradient(circle at 2% 2%, ${alpha(theme.palette.primary.main, 0.15)} 0%, transparent 40%), 
                             radial-gradient(circle at 98% 98%, ${alpha(theme.palette.secondary.main, 0.1)} 0%, transparent 40%),
                             ${theme.palette.background.default}`,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                py: 4
            }}
        >
            <Container maxWidth="lg">
                <Box sx={{ mb: 8, textAlign: 'center' }}>
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.8 }}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2 }}>
                            <CloudQueue sx={{ fontSize: 60, color: 'primary.main', mr: 2 }} />
                            <Typography variant="h2" sx={{ fontWeight: 800, letterSpacing: '-0.02em' }}>
                                FinOps Platform
                            </Typography>
                        </Box>
                        <Typography variant="h5" color="text.secondary" sx={{ maxWidth: 700, mx: 'auto', fontWeight: 400 }}>
                            The enterprise-grade cloud financial operations platform for startups and established organizations.
                        </Typography>
                    </motion.div>
                </Box>

                <Grid container spacing={4} justifyContent="center">
                    {menuItems.map((item, index) => (
                        <Grid item xs={12} md={6} key={item.title}>
                            <motion.div
                                initial={{ opacity: 0, x: index === 0 ? -50 : 50 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ duration: 0.6, delay: index * 0.2 }}
                            >
                                <Card
                                    sx={{
                                        height: '100%',
                                        background: `linear-gradient(135deg, ${alpha(theme.palette.background.paper, 0.8)} 0%, ${alpha(theme.palette.background.paper, 0.4)} 100%)`,
                                        backdropFilter: 'blur(10px)',
                                        border: `1px solid ${alpha(item.color, 0.2)}`,
                                        borderRadius: 4,
                                        transition: 'all 0.3s ease',
                                        '&:hover': {
                                            transform: 'translateY(-8px)',
                                            boxShadow: `0 20px 40px ${alpha(item.color, 0.15)}`,
                                            border: `1px solid ${alpha(item.color, 0.5)}`,
                                        }
                                    }}
                                >
                                    <CardContent sx={{ p: 4, height: '100%', display: 'flex', flexDirection: 'column' }}>
                                        <Box
                                            sx={{
                                                p: 2,
                                                borderRadius: 3,
                                                bgcolor: alpha(item.color, 0.1),
                                                color: item.color,
                                                width: 'fit-content',
                                                mb: 3
                                            }}
                                        >
                                            {item.icon}
                                        </Box>

                                        <Typography variant="h4" gutterBottom sx={{ fontWeight: 700 }}>
                                            {item.title}
                                        </Typography>

                                        <Typography variant="body1" color="text.secondary" sx={{ mb: 4, flexGrow: 1, minHeight: 60 }}>
                                            {item.description}
                                        </Typography>

                                        <Box sx={{ mb: 4 }}>
                                            {item.features.map(f => (
                                                <Box key={f} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                                    <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: item.color, mr: 1.5 }} />
                                                    <Typography variant="body2">{f}</Typography>
                                                </Box>
                                            ))}
                                        </Box>

                                        <Button
                                            variant="contained"
                                            fullWidth
                                            size="large"
                                            onClick={() => navigate(item.path)}
                                            endIcon={<ArrowForward />}
                                            sx={{
                                                py: 2,
                                                borderRadius: 3,
                                                bgcolor: item.color,
                                                '&:hover': {
                                                    bgcolor: alpha(item.color, 0.8)
                                                }
                                            }}
                                        >
                                            Explore Features
                                        </Button>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        </Grid>
                    ))}
                </Grid>

                <Box sx={{ mt: 10, textAlign: 'center', opacity: 0.5 }}>
                    <Typography variant="body2">
                        &copy; 2026 FinOps Platform. Powered by Advanced Agentic Coding.
                    </Typography>
                </Box>
            </Container>
        </Box>
    );
};

export default Home;
