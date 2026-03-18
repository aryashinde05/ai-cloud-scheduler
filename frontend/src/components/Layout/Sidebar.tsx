import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Box,
  Divider,
  Chip,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  TrendingUp as TrendingUpIcon,
  AccountBalance as BudgetIcon,
  Lightbulb as OptimizationIcon,
  Notifications as AlertsIcon,
  Security as ComplianceIcon,
  Settings as SettingsIcon,
  AttachMoney as MoneyIcon,
  EventNote as SchedulerIcon,
  Assessment as ReportsIcon,
  Home as HomeIcon,
  AutoMode as AutoScaleIcon,
  Link as LinkIcon,
  Insights as InsightsIcon,
  Savings as SavingsIcon,
  Storage as AwsIcon,
  Cloud as AzureIcon,
} from '@mui/icons-material';

const drawerWidth = 280;

interface MenuItem {
  text: string;
  icon: React.ReactElement;
  path: string;
  awsOnly?: boolean;
}

interface MenuSection {
  label?: string;
  items: MenuItem[];
}

const menuSections: MenuSection[] = [
  {
    items: [
      { text: 'Home', icon: <HomeIcon />, path: '/' },
      { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { text: 'Smart Scheduler', icon: <SchedulerIcon />, path: '/scheduler', awsOnly: true },
      { text: 'Auto-Scaling Rules', icon: <AutoScaleIcon />, path: '/scaling-rules', awsOnly: true },
      { text: 'Optimization', icon: <OptimizationIcon />, path: '/optimization', awsOnly: true },
    ],
  },
  {
    label: 'Cost Management',
    items: [
      { text: 'Cost Analysis', icon: <TrendingUpIcon />, path: '/cost-analysis' },
      { text: 'Budgets', icon: <BudgetIcon />, path: '/budgets' },
      { text: 'Alerts', icon: <AlertsIcon />, path: '/alerts' },
    ],
  },
  {
    label: 'AWS',
    items: [
      { text: 'AWS Dashboard', icon: <AwsIcon />, path: '/aws/dashboard' },
      { text: 'Connect AWS', icon: <LinkIcon />, path: '/onboarding' },
    ],
  },
  {
    label: 'Azure',
    items: [
      { text: 'Azure Dashboard', icon: <AzureIcon />, path: '/azure/dashboard' },
      { text: 'Connect Azure', icon: <LinkIcon />, path: '/azure/connection' },
      { text: 'Analysis', icon: <InsightsIcon />, path: '/azure/analysis' },
      { text: 'Opportunities', icon: <SavingsIcon />, path: '/azure/opportunities' },
    ],
  },
  {
    label: 'Governance',
    items: [
      { text: 'Compliance', icon: <ComplianceIcon />, path: '/compliance' },
      { text: 'Reports', icon: <ReportsIcon />, path: '/reports' },
    ],
  },
  {
    items: [
      { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
    ],
  },
];

const Sidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: drawerWidth,
          boxSizing: 'border-box',
          background: 'linear-gradient(180deg, #0a0e27 0%, #1a1d3a 100%)',
          borderRight: '1px solid rgba(255, 255, 255, 0.1)',
        },
      }}
    >
      {/* Logo Section */}
      <Box
        onClick={() => navigate('/')}
        sx={{
          p: 3,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          cursor: 'pointer',
          '&:hover': {
            bgcolor: 'rgba(255,255,255,0.02)'
          }
        }}
      >
        <MoneyIcon sx={{ fontSize: 40, color: 'primary.main' }} />
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'white' }}>
            CloudPilot
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Cloud Cost Intelligence
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.1)' }} />

      {/* Navigation Menu */}
      <List sx={{ px: 2, py: 1 }}>
        {menuSections.map((section, sectionIndex) => (
          <React.Fragment key={sectionIndex}>
            {section.label && (
              <Typography
                variant="overline"
                sx={{
                  px: 2,
                  pt: sectionIndex === 0 ? 0 : 1.5,
                  pb: 0.5,
                  display: 'block',
                  color: 'rgba(255,255,255,0.35)',
                  fontSize: '0.65rem',
                  letterSpacing: '0.1em',
                }}
              >
                {section.label}
              </Typography>
            )}
            {!section.label && sectionIndex > 0 && (
              <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', my: 1 }} />
            )}
            {section.items.map((item) => (
              <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  onClick={() => navigate(item.path)}
                  selected={location.pathname === item.path}
                  sx={{
                    borderRadius: 2,
                    '&.Mui-selected': {
                      background: 'linear-gradient(135deg, #2196f3 0%, #1976d2 100%)',
                      '&:hover': {
                        background: 'linear-gradient(135deg, #1976d2 0%, #1565c0 100%)',
                      },
                    },
                    '&:hover': {
                      background: 'rgba(255, 255, 255, 0.05)',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      color: location.pathname === item.path ? 'white' : 'text.secondary',
                      minWidth: 40,
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={item.text}
                    sx={{
                      '& .MuiListItemText-primary': {
                        fontWeight: location.pathname === item.path ? 600 : 400,
                        color: location.pathname === item.path ? 'white' : 'text.primary',
                      },
                    }}
                  />
                  {item.awsOnly && (
                    <Chip
                      label="AWS"
                      size="small"
                      sx={{
                        height: 16,
                        fontSize: '0.6rem',
                        bgcolor: 'rgba(255,152,0,0.15)',
                        color: '#ff9800',
                        border: '1px solid rgba(255,152,0,0.3)',
                        '& .MuiChip-label': { px: 0.75 },
                      }}
                    />
                  )}
                </ListItemButton>
              </ListItem>
            ))}
          </React.Fragment>
        ))}
      </List>

      {/* Status Section */}
      <Box sx={{ mt: 'auto', p: 2 }}>
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            background: 'rgba(76, 175, 80, 0.1)',
            border: '1px solid rgba(76, 175, 80, 0.3)',
          }}
        >
          <Typography variant="caption" sx={{ color: '#4caf50', fontWeight: 600 }}>
            System Status
          </Typography>
          <Typography variant="body2" sx={{ color: 'white', mt: 0.5 }}>
            All systems operational
          </Typography>
        </Box>
      </Box>
    </Drawer>
  );
};

export default Sidebar;