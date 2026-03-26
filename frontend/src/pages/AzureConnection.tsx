import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Button, Paper, Alert, TextField, Grid,
  InputAdornment, IconButton, Stepper, Step, StepLabel,
  StepContent, Chip, Divider, Collapse,
} from '@mui/material';
import {
  Power, CheckCircleOutline, ErrorOutline, Visibility, VisibilityOff,
  Storage, VpnKey, Business, Badge, ExpandMore, ExpandLess,
  OpenInNew, ContentCopy, CheckCircle,
} from '@mui/icons-material';
import { azureCostService } from '../services/azureCostService';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

// UUID v4 pattern
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const isUUID = (v: string) => UUID_RE.test(v.trim());

// Map Azure error codes → friendly messages
function friendlyAzureError(raw: string): { message: string; hint?: string } {
  if (raw.includes('AADSTS700016')) {
    return {
      message: 'The Application (Client) ID was not found in your Azure directory.',
      hint: 'You entered a name or username instead of the Client ID UUID. Go to Azure Portal → App Registrations → your app → copy the "Application (client) ID" (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).',
    };
  }
  if (raw.includes('AADSTS7000215')) {
    return {
      message: 'Invalid client secret value.',
      hint: 'Make sure you copy the Secret VALUE column, not the Secret ID. Go to App Registrations → Certificates & Secrets → copy the value in the "Value" column (not "Secret ID").',
    };
  }
  if (raw.includes('AADSTS90002') || raw.includes('AADSTS900023')) {
    return {
      message: 'Tenant ID not found.',
      hint: 'The Directory (Tenant) ID is incorrect. Go to Azure Portal → Azure Active Directory → Overview → copy the "Tenant ID".',
    };
  }
  if (raw.includes('AADSTS50011')) {
    return {
      message: 'Reply URL mismatch.',
      hint: 'The redirect URI configured in your app registration does not match.',
    };
  }
  if (raw.includes('AuthorizationFailed') || raw.includes('does not have authorization')) {
    return {
      message: 'The Service Principal does not have permission to read this subscription.',
      hint: 'Go to Azure Portal → Subscriptions → your subscription → Access Control (IAM) → Add role assignment → assign "Cost Management Reader" or "Reader" to your app.',
    };
  }
  return { message: raw };
}

const SETUP_STEPS = [
  {
    label: 'Register an App',
    detail: 'Azure Portal → Azure Active Directory → App Registrations → New Registration. Give it any name and click Register.',
    link: 'https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade',
    linkLabel: 'Open App Registrations',
  },
  {
    label: 'Copy Tenant ID & Client ID',
    detail: 'On the app Overview page, copy the "Directory (tenant) ID" and "Application (client) ID". Both are UUIDs in the format xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.',
  },
  {
    label: 'Create a Client Secret',
    detail: 'Go to Certificates & Secrets → New client secret. Set an expiry and click Add. Copy the VALUE column immediately — it is only shown once. Do NOT copy the "Secret ID".',
  },
  {
    label: 'Assign Subscription Permission',
    detail: 'Go to Subscriptions → your subscription → Access Control (IAM) → Add role assignment → select "Cost Management Reader" → assign it to your registered app.',
    link: 'https://portal.azure.com/#view/Microsoft_Azure_Billing/SubscriptionsBlade',
    linkLabel: 'Open Subscriptions',
  },
  {
    label: 'Copy Subscription ID',
    detail: 'On the Subscriptions page, copy the "Subscription ID" UUID next to your subscription name.',
  },
];

export default function AzureConnection() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorInfo, setErrorInfo] = useState<{ message: string; hint?: string } | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [copied, setCopied] = useState('');

  const [credentials, setCredentials] = useState({
    tenant_id: '',
    client_id: '',
    client_secret: '',
    subscription_id: '',
  });

  // Field-level validation errors
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const saved = azureCostService.getStoredCredentials();
    if (saved?.tenant_id) {
      setCredentials(prev => ({ ...prev, ...saved, client_secret: '' }));
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setCredentials(prev => ({ ...prev, [name]: value }));
    // Clear field error on change
    if (fieldErrors[name]) {
      setFieldErrors(prev => ({ ...prev, [name]: '' }));
    }
    setStatus('idle');
  };

  const validateFields = () => {
    const errors: Record<string, string> = {};
    const uuidFields = ['tenant_id', 'client_id', 'subscription_id'] as const;
    const labels: Record<string, string> = {
      tenant_id: 'Directory (Tenant) ID',
      client_id: 'Application (Client) ID',
      subscription_id: 'Subscription ID',
    };

    for (const field of uuidFields) {
      const val = credentials[field].trim();
      if (!val) {
        errors[field] = `${labels[field]} is required`;
      } else if (!isUUID(val)) {
        errors[field] = `Must be a UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx) — not a name or email`;
      }
    }

    if (!credentials.client_secret.trim()) {
      errors.client_secret = 'Client Secret is required';
    }

    return errors;
  };

  const handleTestConnection = async () => {
    const errors = validateFields();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setLoading(true);
    setStatus('idle');
    setErrorInfo(null);
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
      const raw: string = err.response?.data?.detail || err.message || 'Failed to connect to Azure.';
      setErrorInfo(friendlyAzureError(raw));
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key);
      setTimeout(() => setCopied(''), 2000);
    });
  };

  const uuidFieldProps = (name: keyof typeof credentials, label: string, icon: React.ReactNode) => ({
    fullWidth: true,
    label,
    name,
    value: credentials[name],
    onChange: handleChange,
    variant: 'outlined' as const,
    placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
    error: !!fieldErrors[name],
    helperText: fieldErrors[name] || ' ',
    InputProps: {
      startAdornment: <InputAdornment position="start">{icon}</InputAdornment>,
      endAdornment: credentials[name] && isUUID(credentials[name]) ? (
        <InputAdornment position="end">
          <CheckCircle sx={{ color: 'success.main', fontSize: 18 }} />
        </InputAdornment>
      ) : undefined,
    },
  });

  return (
    <Box sx={{ maxWidth: 860, mx: 'auto', mt: 4 }}>
      <Helmet><title>Azure Connection | FinOps</title></Helmet>

      <Box sx={{ mb: 4 }}>
        <Button variant="text" color="inherit" onClick={() => navigate('/dashboard')} sx={{ opacity: 0.6, mb: 2, p: 0 }}>
          ← Back to Dashboard
        </Button>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Connect Azure Account
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure a Service Principal to allow the platform to analyse your Azure cloud costs.
        </Typography>
      </Box>

      {/* Setup guide toggle */}
      <Paper
        sx={{ mb: 3, borderRadius: 3, border: '1px solid rgba(33,150,243,0.2)', bgcolor: 'rgba(33,150,243,0.04)', overflow: 'hidden' }}
      >
        <Box
          sx={{ px: 3, py: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
          onClick={() => setShowGuide(v => !v)}
        >
          <Box>
            <Typography variant="subtitle1" fontWeight={600} color="primary.main">
              📋 Step-by-step setup guide
            </Typography>
            <Typography variant="caption" color="text.secondary">
              New to Azure Service Principals? Follow these steps first.
            </Typography>
          </Box>
          {showGuide ? <ExpandLess color="primary" /> : <ExpandMore color="primary" />}
        </Box>

        <Collapse in={showGuide}>
          <Divider sx={{ borderColor: 'rgba(33,150,243,0.15)' }} />
          <Box sx={{ px: 3, py: 2 }}>
            <Stepper orientation="vertical" nonLinear>
              {SETUP_STEPS.map((step, i) => (
                <Step key={i} active>
                  <StepLabel>
                    <Typography variant="body2" fontWeight={600}>{step.label}</Typography>
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {step.detail}
                    </Typography>
                    {step.link && (
                      <Button
                        size="small"
                        endIcon={<OpenInNew fontSize="small" />}
                        href={step.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ mb: 1 }}
                      >
                        {step.linkLabel}
                      </Button>
                    )}
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          </Box>
        </Collapse>
      </Paper>

      {/* Credentials form */}
      <Paper sx={{ p: 4, borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none', border: '1px solid rgba(255,255,255,0.05)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 4, gap: 2 }}>
          <Box sx={{ width: 48, height: 48, borderRadius: 3, bgcolor: 'rgba(33,150,243,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'primary.main' }}>
            <Power sx={{ fontSize: 28 }} />
          </Box>
          <Box>
            <Typography variant="h6" fontWeight={600}>Service Principal Credentials</Typography>
            <Typography variant="body2" color="text.secondary">All four fields are required. Each ID must be a UUID.</Typography>
          </Box>
        </Box>

        <Grid container spacing={3} mb={2}>
          <Grid item xs={12} md={6}>
            <TextField {...uuidFieldProps('tenant_id', 'Directory (Tenant) ID', <Business fontSize="small" color="action" />)} />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField {...uuidFieldProps('client_id', 'Application (Client) ID', <Badge fontSize="small" color="action" />)} />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Client Secret Value"
              name="client_secret"
              value={credentials.client_secret}
              onChange={handleChange}
              type={showSecret ? 'text' : 'password'}
              variant="outlined"
              placeholder="Paste the secret VALUE (not the Secret ID)"
              error={!!fieldErrors.client_secret}
              helperText={fieldErrors.client_secret || 'Copy from Certificates & Secrets → Value column'}
              InputProps={{
                startAdornment: <InputAdornment position="start"><VpnKey fontSize="small" color="action" /></InputAdornment>,
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={() => setShowSecret(!showSecret)} edge="end" size="small">
                      {showSecret ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField {...uuidFieldProps('subscription_id', 'Subscription ID', <Storage fontSize="small" color="action" />)} />
          </Grid>
        </Grid>

        {/* UUID format reminder */}
        <Alert severity="info" sx={{ mb: 3, borderRadius: 2 }}>
          <Typography variant="body2">
            <strong>All IDs must be UUIDs</strong> — format: <code>xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</code>.
            If you're pasting a name, email, or display name, that's the wrong value.
          </Typography>
        </Alert>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
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

        {status === 'error' && errorInfo && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Alert
              icon={<ErrorOutline fontSize="inherit" />}
              severity="error"
              sx={{ mt: 3, borderRadius: 2 }}
            >
              <Typography variant="body2" fontWeight={600} sx={{ mb: errorInfo.hint ? 0.5 : 0 }}>
                {errorInfo.message}
              </Typography>
              {errorInfo.hint && (
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  💡 {errorInfo.hint}
                </Typography>
              )}
            </Alert>
          </motion.div>
        )}
      </Paper>

      {/* Quick reference */}
      <Paper sx={{ mt: 3, p: 3, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>Where to find each value</Typography>
        <Grid container spacing={2} sx={{ mt: 0.5 }}>
          {[
            { label: 'Tenant ID', where: 'Azure Active Directory → Overview → Tenant ID' },
            { label: 'Client ID', where: 'App Registrations → your app → Application (client) ID' },
            { label: 'Client Secret', where: 'App Registrations → your app → Certificates & Secrets → Value column' },
            { label: 'Subscription ID', where: 'Subscriptions → Subscription ID column' },
          ].map(item => (
            <Grid item xs={12} sm={6} key={item.label}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <Chip label={item.label} size="small" sx={{ bgcolor: 'rgba(33,150,243,0.12)', color: 'primary.light', flexShrink: 0 }} />
                <Typography variant="caption" color="text.secondary">{item.where}</Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Paper>
    </Box>
  );
}
