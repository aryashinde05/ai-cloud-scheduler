import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
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

// Lazy-loaded pages for code splitting
const OnboardingQuickStart = lazy(() => import('./pages/OnboardingQuickStart'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
// AWS-specific dashboard (cost/resources view)
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
const Home = lazy(() => import('./pages/Home'));
const MigrationWizard = lazy(() => import('./pages/MigrationWizard'));
const MigrationResults = lazy(() => import('./pages/MigrationResults'));
const MigrationDashboard = lazy(() => import('./pages/MigrationDashboard'));
const ProviderRecommendations = lazy(() => import('./pages/ProviderRecommendations'));
const ResourceOrganization = lazy(() => import('./pages/ResourceOrganization'));
const DimensionalFiltering = lazy(() => import('./pages/DimensionalFiltering'));
const MigrationReport = lazy(() => import('./pages/MigrationReport'));
const PlatformFloatingChat = lazy(() => import('./components/AI/PlatformFloatingChat'));

// New Azure Pages
const AzureDashboard = lazy(() => import('./pages/AzureDashboard'));
const AzureConnection = lazy(() => import('./pages/AzureConnection'));
const AzureAnalysis = lazy(() => import('./pages/AzureAnalysis'));
const AzureOpportunities = lazy(() => import('./pages/AzureOpportunities'));

// New AWS Pages
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

// Reusable layout wrapper with Suspense
const PageLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
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

const ProtectedPage = ({ children }: { children: React.ReactElement }) => (
  <ProtectedRoute>
    <PageLayout>{children}</PageLayout>
  </ProtectedRoute>
);

const ProtectedRouteWrapper = ({ children }: { children: React.ReactElement }) => (
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
                    {/* Public Routes */}
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/" element={<Home />} />
                    
                    {/* Protected Routes */}
                    <Route path="/onboarding" element={<ProtectedRouteWrapper><OnboardingQuickStart /></ProtectedRouteWrapper>} />

                    {/* Migration Wizard - Protected */}
                    <Route path="/migration-wizard" element={<ProtectedRouteWrapper><MigrationWizard /></ProtectedRouteWrapper>} />
                    <Route path="/migration-wizard/:projectId" element={<ProtectedRouteWrapper><MigrationWizard /></ProtectedRouteWrapper>} />
                    <Route path="/migration/:projectId/recommendations" element={<ProtectedRouteWrapper><ProviderRecommendations /></ProtectedRouteWrapper>} />
                    <Route path="/migration/:projectId/results" element={<ProtectedRouteWrapper><MigrationResults /></ProtectedRouteWrapper>} />
                    <Route path="/migration/:projectId/dashboard" element={<ProtectedRouteWrapper><MigrationDashboard /></ProtectedRouteWrapper>} />
                    <Route path="/migration/:projectId/resources" element={<ProtectedRouteWrapper><ResourceOrganization /></ProtectedRouteWrapper>} />
                    <Route path="/migration/:projectId/filtering" element={<ProtectedRouteWrapper><DimensionalFiltering /></ProtectedRouteWrapper>} />
                    <Route path="/migration/:projectId/report" element={<ProtectedRouteWrapper><MigrationReport /></ProtectedRouteWrapper>} />

                    {/* Dashboard Routes - Protected */}
                    <Route path="/dashboard" element={<ProtectedPage><Dashboard /></ProtectedPage>} />
                    <Route path="/aws/dashboard" element={<ProtectedPage><AwsDashboard /></ProtectedPage>} />
                    <Route path="/scheduler" element={<ProtectedPage><SchedulerDashboard /></ProtectedPage>} />
                    <Route path="/scaling-rules" element={<ProtectedPage><ScalingRules /></ProtectedPage>} />
                    <Route path="/cost-analysis" element={<ProtectedPage><CostAnalysis /></ProtectedPage>} />
                    <Route path="/budgets" element={<ProtectedPage><BudgetManagement /></ProtectedPage>} />
                    <Route path="/optimization" element={<ProtectedPage><Optimization /></ProtectedPage>} />
                    <Route path="/reports" element={<ProtectedPage><Reports /></ProtectedPage>} />
                    <Route path="/alerts" element={<ProtectedPage><Alerts /></ProtectedPage>} />
                    <Route path="/compliance" element={<ProtectedPage><Compliance /></ProtectedPage>} />
                    <Route path="/settings" element={<ProtectedPage><Settings /></ProtectedPage>} />

                    {/* Azure Routes - Protected */}
                    <Route path="/azure/dashboard" element={<ProtectedPage><AzureDashboard /></ProtectedPage>} />
                    <Route path="/azure/connection" element={<ProtectedPage><AzureConnection /></ProtectedPage>} />
                    <Route path="/azure/analysis" element={<ProtectedPage><AzureAnalysis /></ProtectedPage>} />
                    <Route path="/azure/opportunities" element={<ProtectedPage><AzureOpportunities /></ProtectedPage>} />

                    {/* AWS Routes - Protected */}
                    <Route path="/aws/connection" element={<ProtectedPage><AwsConnection /></ProtectedPage>} />
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