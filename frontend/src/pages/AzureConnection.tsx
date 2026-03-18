import React, { useState, useEffect } from 'react';
import { Box, Typography, Button, Paper, Alert, TextField, Grid, InputAdornment, IconButton } from '@mui/material';
import { azureCostService } from '../services/azureCostService';
import { Power, CheckCircleOutline, ErrorOutline, Visibility, VisibilityOff, Storage, VpnKey, Business, Badge } from '@mui/icons-material';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

export default function AzureConnection() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  
  const [credentials, setCredentials] = useState({
    tenant_id: '',
    client_id: '',
    client_secret: '',
    subscription_id: ''
  });

  useEffect(() => {
    const saved = azureCostService.getStoredCredentials();
    if (saved && saved.tenant_id) {
      setCredentials(prev => ({
        ...prev,
        ...saved,
        client_secret: '' // Security: don't pre-fill secret if it matches placeholder or empty
      }));
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCredentials({ ...credentials, [e.target.name]: e.target.value });
  };

  const handleTestConnection = async () => {
    if (!credentials.tenant_id || !credentials.client_id || !credentials.client_secret || !credentials.subscription_id) {
      setStatus('error');
      setErrorMessage('Please fill in all Azure credential fields.');
      return;
    }

    setLoading(true);
    setStatus('idle');
    try {
      const result = await azureCostService.testConnection(credentials);
      if (result.status === 'success') {
        localStorage.setItem('azure_credentials', JSON.stringify(credentials));
        setStatus('success');
      } else {
        throw new Error(result.message || 'Connection test failed');
      }
    } catch (err: any) {
      setStatus('error');
      const rawMsg: string = err.response?.data?.detail || err.message || 'Failed to connect to Azure APIs.';
      // Provide a friendlier hint for the most common Azure auth mistake
      const friendlyMsg = rawMsg.includes('AADSTS7000215')
        ? 'Invalid client secret. Make sure you are entering the Secret VALUE (not the Secret ID) from Azure Portal → App Registrations → Certificates & Secrets.'
        : rawMsg;
      setErrorMessage(friendlyMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', mt: 4 }}>
      <Helmet><title>Azure Connection | FinOps</title></Helmet>
      
      <Box sx={{ mb: 4 }}>
        <Button variant="text" color="inherit" onClick={() => navigate('/dashboard')} sx={{ opacity: 0.6, mb: 2, p: 0 }}>
          ← Back to Dashboard
        </Button>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Connect Azure Account
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure a Service Principal to allow our platform to analyze your Azure cloud costs.
        </Typography>
      </Box>

      <Paper sx={{ p: 4, borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none', border: '1px solid rgba(255,255,255,0.05)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 5, gap: 2 }}>
          <Box sx={{ 
            width: 56, height: 56, borderRadius: 3, 
            bgcolor: 'rgba(33, 150, 243, 0.1)', 
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'primary.main'
          }}>
            <Power sx={{ fontSize: 32 }} />
          </Box>
          <Box>
            <Typography variant="h6" fontWeight={600}>Service Principal Auth</Typography>
            <Typography variant="body2" color="text.secondary">Use Client Credentials flow for API access</Typography>
          </Box>
        </Box>

        <Grid container spacing={3} mb={4}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Directory (Tenant) ID"
              name="tenant_id"
              value={credentials.tenant_id}
              onChange={handleChange}
              variant="outlined"
              placeholder="xxxxxxxx-xxxx..."
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Business fontSize="small" color="action" />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Application (Client) ID"
              name="client_id"
              value={credentials.client_id}
              onChange={handleChange}
              variant="outlined"
              placeholder="xxxxxxxx-xxxx..."
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Badge fontSize="small" color="action" />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={6}>
             <TextField
              fullWidth
              label="Client Secret"
              name="client_secret"
              value={credentials.client_secret}
              onChange={handleChange}
              type={showSecret ? 'text' : 'password'}
              variant="outlined"
              placeholder="Enter your secret key"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <VpnKey fontSize="small" color="action" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={() => setShowSecret(!showSecret)} edge="end">
                      {showSecret ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={6}>
             <TextField
              fullWidth
              label="Subscription ID"
              name="subscription_id"
              value={credentials.subscription_id}
              onChange={handleChange}
              variant="outlined"
              placeholder="xxxxxxxx-xxxx..."
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Storage fontSize="small" color="action" />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Button 
            variant="contained" 
            color="primary" 
            size="large"
            disabled={loading}
            onClick={handleTestConnection}
            sx={{ px: 4, py: 1.5, borderRadius: 2, fontWeight: 600 }}
          >
            {loading ? 'Validating...' : 'Verify & Save Connection'}
          </Button>
          
          {status === 'success' && (
            <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', color: 'success.main', gap: 1 }}>
                <CheckCircleOutline />
                <Typography variant="body2" fontWeight={600}>Connected Successfully</Typography>
              </Box>
            </motion.div>
          )}
        </Box>

        {status === 'error' && (
          <Box sx={{ mt: 3 }}>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <Alert icon={<ErrorOutline fontSize="inherit" />} severity="error" sx={{ borderRadius: 2 }}>
                {errorMessage}
              </Alert>
            </motion.div>
          </Box>
        )}
      </Paper>

      <Box sx={{ mt: 6, p: 3, borderRadius: 4, bgcolor: 'rgba(33, 150, 243, 0.05)', border: '1px dashed rgba(33, 150, 243, 0.2)' }}>
        <Typography variant="subtitle2" color="primary.main" gutterBottom fontWeight={600}>Helpful Tip</Typography>
        <Typography variant="body2" color="text.secondary">
          You can create a Service Principal in the Azure Portal under <b>Azure Active Directory &gt; App Registrations</b>. 
          Ensure it has at least 'Reader' or 'Cost Management Reader' permissions on the subscription.
        </Typography>
      </Box>
    </Box>
  );
}
