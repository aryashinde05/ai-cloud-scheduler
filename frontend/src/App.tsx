import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';
import { HelmetProvider } from 'react-helmet-async';

import { AuthProvider } from './contexts/AuthContext';
import { NotificationProvider } from './contexts/NotificationContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Register from './pages/Register';

// Components (always loaded)
import Sidebar from './components/Layout/Sidebar';
import Header from './components/Layout/Header';
import ErrorBoundary from './components/ErrorBoundary';
import { LoadingSpinner } from './components/Loading';

// Lazy-loaded pages
const OnboardingQuickStart = lazy(() => import('./pages/OnboardingQuickStart'));
const ServiceSelection = lazy(() => import('./pages/ServiceSelection'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AwsDashboard = lazy(() => import('./pages/AwsDashboard'));
const CostAnalysis = lazy(() => import('./pages/CostAnalysis'));
const BudgetManagement = lazy(() => import('./pages/BudgetManagement'));
const Optimization = lazy(() => import('./pages/Optimization'));
const Reports = lazy(() => import('./pages/Reports'));
const Settings = lazy(() => import('./pages/Settings'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Compliance = lazy(() => import('./pages/Compliance'));
const SchedulerDashboard = lazy(() => import('./pages/SchedulerDashboard'));
const ScalingRules = lazy(() => import('./pages/ScalingRules'));
const MigrationWizard = lazy(() => import('./pages/MigrationWizard'));
const PlatformFloatingChat = lazy(() => import('./components/AI/PlatformFloatingChat'));

// Azure Pages
const AzureDashboard = lazy(() => import('./pages/AzureDashboard'));
const AzureConnection = lazy(() => import('./pages/AzureConnection'));
const AzureAnalysis = lazy(() => import('./pages/AzureAnalysis'));
const AzureOpportunities = lazy(() => import('./pages/AzureOpportunities'));

// AWS Pages
const AwsConnection = lazy(() => import('./pages/AwsConnection'));

// Theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#2196f3',
      light: '#64b5f6',
      dark: '#1976d2',
    },
    secondary: {
      main: '#f50057',
      light: '#ff5983',
      dark: '#c51162',
    },
    background: {
      default: '#0a0e27',
      paper: '#1a1d3a',
    },
    text: {
      primary: '#ffffff',
      secondary: '#b0bec5',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 500,
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'linear-gradient(135deg, #1a1d3a 0%, #2a2d5a 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
        },
      },
    },
  },
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Dashboard shell: sidebar + header
const DashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box sx={{ display: 'flex', minHeight: '100vh' }}>
    <Sidebar />
    <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
      <Header />
      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
        <Suspense fallback={<LoadingSpinner />}>
          {children}
        </Suspense>
      </Box>
    </Box>
  </Box>
);

// Migration shell: no sidebar, just a top bar (Header handles user/logout)
const MigrationLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
    <Header />
    <Box component="main" sx={{ flexGrow: 1, mt: 8 }}>
      <Suspense fallback={<LoadingSpinner />}>
        {children}
      </Suspense>
    </Box>
  </Box>
);

const ProtectedDashboard = ({ children }: { children: React.ReactElement }) => (
  <ProtectedRoute>
    <DashboardLayout>{children}</DashboardLayout>
  </ProtectedRoute>
);

const ProtectedMigration = ({ children }: { children: React.ReactElement }) => (
  <ProtectedRoute>
    <MigrationLayout>{children}</MigrationLayout>
  </ProtectedRoute>
);

const ProtectedFull = ({ children }: { children: React.ReactElement }) => (
  <ProtectedRoute>{children}</ProtectedRoute>
);

function App() {
  return (
    <ErrorBoundary>
      <HelmetProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <NotificationProvider>
            <ThemeProvider theme={theme}>
              <CssBaseline />
              <Router>
                <Suspense fallback={<LoadingSpinner />}>
                  <Routes>
                    {/* Public routes */}
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/" element={<Navigate to="/login" replace />} />

                    {/* Service selection — protected, no sidebar */}
                    <Route path="/select" element={
                      <ProtectedFull><Suspense fallback={<LoadingSpinner />}><ServiceSelection /></Suspense></ProtectedFull>
                    } />

                    {/* Onboarding — protected, no sidebar */}
                    <Route path="/onboarding" element={
                      <ProtectedFull><Suspense fallback={<LoadingSpinner />}><OnboardingQuickStart /></Suspense></ProtectedFull>
                    } />

                    {/* ── Migration module — isolated, no sidebar ── */}
                    <Route path="/migration-wizard" element={<ProtectedMigration><MigrationWizard /></ProtectedMigration>} />
                    <Route path="/migration-wizard/:projectId" element={<ProtectedMigration><MigrationWizard /></ProtectedMigration>} />

                    {/* ── Cloud Dashboard module — sidebar layout ── */}
                    <Route path="/dashboard" element={<ProtectedDashboard><Dashboard /></ProtectedDashboard>} />
                    <Route path="/aws/dashboard" element={<ProtectedDashboard><AwsDashboard /></ProtectedDashboard>} />
                    <Route path="/scheduler" element={<ProtectedDashboard><SchedulerDashboard /></ProtectedDashboard>} />
                    <Route path="/scaling-rules" element={<ProtectedDashboard><ScalingRules /></ProtectedDashboard>} />
                    <Route path="/cost-analysis" element={<ProtectedDashboard><CostAnalysis /></ProtectedDashboard>} />
                    <Route path="/budgets" element={<ProtectedDashboard><BudgetManagement /></ProtectedDashboard>} />
                    <Route path="/optimization" element={<ProtectedDashboard><Optimization /></ProtectedDashboard>} />
                    <Route path="/reports" element={<ProtectedDashboard><Reports /></ProtectedDashboard>} />
                    <Route path="/alerts" element={<ProtectedDashboard><Alerts /></ProtectedDashboard>} />
                    <Route path="/compliance" element={<ProtectedDashboard><Compliance /></ProtectedDashboard>} />
                    <Route path="/settings" element={<ProtectedDashboard><Settings /></ProtectedDashboard>} />

                    {/* Azure routes */}
                    <Route path="/azure/dashboard" element={<ProtectedDashboard><AzureDashboard /></ProtectedDashboard>} />
                    <Route path="/azure/connection" element={<ProtectedDashboard><AzureConnection /></ProtectedDashboard>} />
                    <Route path="/azure/analysis" element={<ProtectedDashboard><AzureAnalysis /></ProtectedDashboard>} />
                    <Route path="/azure/opportunities" element={<ProtectedDashboard><AzureOpportunities /></ProtectedDashboard>} />

                    {/* AWS routes */}
                    <Route path="/aws/connection" element={<ProtectedDashboard><AwsConnection /></ProtectedDashboard>} />
                  </Routes>
                  <PlatformFloatingChat />
                </Suspense>
              </Router>
              <Toaster
                position="top-right"
                toastOptions={{
                  duration: 4000,
                  style: {
                    background: '#1a1d3a',
                    color: '#fff',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  },
                }}
              />
            </ThemeProvider>
            </NotificationProvider>
          </AuthProvider>
        </QueryClientProvider>
      </HelmetProvider>
    </ErrorBoundary>
  );
}

export default App;