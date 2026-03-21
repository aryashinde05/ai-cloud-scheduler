import React from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  Button,
  alpha,
  useTheme,
  Chip,
} from '@mui/material';
import {
  MonitorHeart,
  MoveToInbox,
  ArrowForward,
  Logout,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const services = [
  {
    id: 'dashboard',
    title: 'Cloud Dashboard',
    subtitle: 'Monitor & Optimise',
    description:
      'Connect AWS or Azure and get real-time cost analysis, resource scheduling, budget alerts, and AI-powered optimisation recommendations.',
    icon: <MonitorHeart sx={{ fontSize: 56 }} />,
    color: '#2196f3',
    path: '/dashboard',
    features: ['AWS Cost Analysis', 'Azure Cost Control', 'Smart Scheduler', 'Budget Alerts'],
    badge: null,
  },
  {
    id: 'migration',
    title: 'Cloud Migration',
    subtitle: 'Plan Your Move',
    description:
      'Plan your journey from on-premises to the cloud. Get provider recommendations, migration complexity estimates, and a step-by-step roadmap.',
    icon: <MoveToInbox sx={{ fontSize: 56 }} />,
    color: '#ff9800',
    path: '/migration-wizard',
    features: ['Provider Scoring (AWS / Azure / GCP)', 'Migration Complexity', 'Cost Estimation', 'Compliance Check'],
    badge: 'No cloud account needed',
  },
];

const ServiceSelection: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `radial-gradient(ellipse at 10% 10%, ${alpha('#2196f3', 0.12)} 0%, transparent 50%),
                     radial-gradient(ellipse at 90% 90%, ${alpha('#ff9800', 0.10)} 0%, transparent 50%),
                     #0a0e27`,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top bar */}
      <Box
        sx={{
          px: 4,
          py: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700, color: 'white', letterSpacing: '-0.01em' }}>
          CloudPilot
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {user && (
            <Typography variant="body2" color="text.secondary">
              {user.first_name} {user.last_name}
            </Typography>
          )}
          <Button
            size="small"
            startIcon={<Logout fontSize="small" />}
            onClick={handleLogout}
            sx={{ color: 'text.secondary', '&:hover': { color: 'white' } }}
          >
            Sign out
          </Button>
        </Box>
      </Box>

      {/* Main content */}
      <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
        <Container maxWidth="lg">
          <motion.div
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Box sx={{ textAlign: 'center', mb: 8 }}>
              <Typography
                variant="h3"
                sx={{ fontWeight: 800, mb: 1.5, letterSpacing: '-0.02em' }}
              >
                What would you like to do?
              </Typography>
              <Typography variant="h6" color="text.secondary" fontWeight={400}>
                Choose a module to get started
              </Typography>
            </Box>
          </motion.div>

          <Grid container spacing={4} justifyContent="center">
            {services.map((svc, idx) => (
              <Grid item xs={12} md={5} key={svc.id}>
                <motion.div
                  initial={{ opacity: 0, y: 30 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: idx * 0.15 }}
                  style={{ height: '100%' }}
                >
                  <Card
                    sx={{
                      height: '100%',
                      border: `1px solid ${alpha(svc.color, 0.2)}`,
                      background: `linear-gradient(145deg, ${alpha(theme.palette.background.paper, 0.9)} 0%, ${alpha(theme.palette.background.paper, 0.6)} 100%)`,
                      backdropFilter: 'blur(12px)',
                      borderRadius: 4,
                      cursor: 'pointer',
                      transition: 'all 0.25s ease',
                      '&:hover': {
                        transform: 'translateY(-6px)',
                        border: `1px solid ${alpha(svc.color, 0.55)}`,
                        boxShadow: `0 24px 48px ${alpha(svc.color, 0.18)}`,
                      },
                    }}
                    onClick={() => navigate(svc.path)}
                  >
                    <CardContent sx={{ p: 4, display: 'flex', flexDirection: 'column', height: '100%' }}>
                      {/* Icon */}
                      <Box
                        sx={{
                          p: 2,
                          borderRadius: 3,
                          bgcolor: alpha(svc.color, 0.12),
                          color: svc.color,
                          width: 'fit-content',
                          mb: 3,
                        }}
                      >
                        {svc.icon}
                      </Box>

                      {/* Title */}
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
                        <Typography variant="h4" sx={{ fontWeight: 700 }}>
                          {svc.title}
                        </Typography>
                        {svc.badge && (
                          <Chip
                            label={svc.badge}
                            size="small"
                            sx={{
                              bgcolor: alpha(svc.color, 0.15),
                              color: svc.color,
                              border: `1px solid ${alpha(svc.color, 0.3)}`,
                              fontSize: '0.65rem',
                              fontWeight: 600,
                            }}
                          />
                        )}
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, fontWeight: 500 }}>
                        {svc.subtitle}
                      </Typography>

                      <Typography variant="body1" color="text.secondary" sx={{ mb: 4, flexGrow: 1, lineHeight: 1.7 }}>
                        {svc.description}
                      </Typography>

                      {/* Feature list */}
                      <Box sx={{ mb: 4 }}>
                        {svc.features.map((f) => (
                          <Box key={f} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: svc.color,
                                mr: 1.5,
                                flexShrink: 0,
                              }}
                            />
                            <Typography variant="body2">{f}</Typography>
                          </Box>
                        ))}
                      </Box>

                      <Button
                        variant="contained"
                        fullWidth
                        size="large"
                        endIcon={<ArrowForward />}
                        onClick={(e) => { e.stopPropagation(); navigate(svc.path); }}
                        sx={{
                          py: 1.75,
                          borderRadius: 3,
                          bgcolor: svc.color,
                          fontWeight: 600,
                          '&:hover': { bgcolor: alpha(svc.color, 0.85) },
                        }}
                      >
                        Open {svc.title}
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      <Box sx={{ py: 3, textAlign: 'center', opacity: 0.35 }}>
        <Typography variant="caption">© 2026 CloudPilot · FinOps Platform</Typography>
      </Box>
    </Box>
  );
};

export default ServiceSelection;
