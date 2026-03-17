import React, { useState, useEffect } from 'react';
import { Box, Typography, Grid, Paper, Tabs, Tab, CircularProgress, Alert, Button } from '@mui/material';
import { useQuery } from 'react-query';
import { azureCostService } from '../services/azureCostService';
import { OpportunityCard } from '../components/Azure/OpportunityCard';
import { Helmet } from 'react-helmet-async';
import { 
  History, 
  SettingsInputComponent, 
  Autorenew, 
  SentimentVeryDissatisfied 
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

const TABS = [
  { label: 'Reserved Instances', value: 'reserved_instances', icon: <History /> },
  { label: 'Rightsizing', value: 'rightsizing', icon: <SettingsInputComponent /> },
  { label: 'Idle Resources', value: 'unused_resources', icon: <Autorenew /> }
];

export default function AzureOpportunities() {
  const [activeTab, setActiveTab] = useState('reserved_instances');
  const [hasCredentials, setHasCredentials] = useState(false);

  useEffect(() => {
    const creds = localStorage.getItem('azure_credentials');
    setHasCredentials(!!creds);
  }, []);

  const { data: opportunities, isLoading, error } = useQuery(
    ['azureOpportunities', activeTab],
    () => azureCostService.getOpportunities(activeTab),
    { enabled: hasCredentials, keepPreviousData: true }
  );

  const handleTabChange = (_: any, newValue: string) => {
    setActiveTab(newValue);
  };

  if (!hasCredentials) {
    return (
      <Box p={4} textAlign="center">
        <Typography variant="h5">Please connect your Azure account first.</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Helmet><title>Optimization Opportunities | Azure</title></Helmet>
      
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Optimization Opportunities
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Actionable recommendations to reduce your cloud bill without impacting performance.
        </Typography>
      </Box>

      <Paper sx={{ mb: 4, borderRadius: 2, bgcolor: 'background.paper', backgroundImage: 'none' }}>
        <Tabs 
          value={activeTab} 
          onChange={handleTabChange} 
          variant="fullWidth"
          indicatorColor="primary"
          textColor="primary"
        >
          {TABS.map(tab => (
            <Tab 
              key={tab.value} 
              icon={tab.icon} 
              label={tab.label} 
              value={tab.value} 
              sx={{ py: 2, minHeight: 72 }}
            />
          ))}
        </Tabs>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 4, borderRadius: 2 }}>
          Failed to load opportunities. Please verify your Azure permissions.
        </Alert>
      )}

      {isLoading ? (
        <Box display="flex" justifyContent="center" py={10}>
          <CircularProgress />
        </Box>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
          >
            {opportunities && opportunities.length > 0 ? (
              <Grid container spacing={3}>
                {opportunities.map((opp: any, index: number) => (
                  <Grid item xs={12} md={6} key={index}>
                    <OpportunityCard 
                      service={opp.service}
                      type={opp.opportunity_type}
                      cost={opp.current_monthly_cost}
                      savings={opp.potential_monthly_savings}
                      confidence={opp.confidence_level}
                      description={opp.description}
                      action={opp.action_required}
                    />
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Paper sx={{ p: 8, textAlign: 'center', borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none' }}>
                <SentimentVeryDissatisfied sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6">No opportunities found</Typography>
                <Typography color="text.secondary">
                  Great job! Your Azure infrastructure seems well optimized for this category.
                </Typography>
              </Paper>
            )}
          </motion.div>
        </AnimatePresence>
      )}
    </Box>
  );
}
