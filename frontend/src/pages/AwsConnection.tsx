import React, { useState } from 'react';
import { Box, Typography, Button, Paper, Alert, TextField, Grid, MenuItem } from '@mui/material';
import { awsService } from '../services/awsService';
import { Cloud, CheckCircleOutline, ErrorOutline } from '@mui/icons-material';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

const COMMON_REGIONS = [
  "us-east-1",
  "us-east-2",
  "us-west-1",
  "us-west-2",
  "eu-west-1",
  "eu-central-1",
  "ap-south-1",
  "ap-southeast-1",
  "ap-southeast-2",
  "ap-northeast-1"
];

export default function AwsConnection() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [currentRegion, setCurrentRegion] = useState<string | null>(null);
  
  const [credentials, setCredentials] = useState({
    access_key: '',
    secret_key: '',
    region: 'us-east-1'
  });

  React.useEffect(() => {
    awsService.getStatus().then((s: any) => {
      if (s?.connected && s?.region) {
        setCurrentRegion(s.region);
        setCredentials(prev => ({ ...prev, region: s.region }));
      }
    }).catch(() => {});
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCredentials({ ...credentials, [e.target.name]: e.target.value });
  };

  const handleConnect = async () => {
    if (!credentials.access_key || !credentials.secret_key || !credentials.region) {
      setStatus('error');
      setErrorMessage('Please fill in all AWS credential fields.');
      return;
    }

    setLoading(true);
    setStatus('idle');
    try {
      await awsService.connect(credentials);
      setStatus('success');
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.response?.data?.detail || err.message || 'Failed to connect to AWS.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', mt: 4 }}>
      <Helmet><title>AWS Connection | FinOps</title></Helmet>
      
      <Typography variant="h4" fontWeight={700} gutterBottom>
        AWS Connection
      </Typography>
      <Typography variant="body1" color="text.secondary" mb={4}>
        Connect your AWS account to enable cost analysis and resource optimization.
      </Typography>

      <Paper sx={{ p: 4, borderRadius: 4, bgcolor: 'background.paper', backgroundImage: 'none' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 4, flexDirection: 'column' }}>
          <Box sx={{ 
            width: 64, height: 64, borderRadius: '50%', 
            bgcolor: 'rgba(255, 153, 0, 0.1)', 
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#FF9900', // AWS Orange
            mb: 2
          }}>
            <Cloud sx={{ fontSize: 32 }} />
          </Box>
          <Typography variant="h6" align="center">
            AWS Credentials
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            Enter your IAM Access Key and Secret Key.
          </Typography>
        </Box>

        <Grid container spacing={3} mb={3}>
          {currentRegion && (
            <Grid item xs={12}>
              <Alert severity="info">
                Currently connected to region: <strong>{currentRegion}</strong>. Enter your credentials below to update or change region.
              </Alert>
            </Grid>
          )}
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Access Key ID"
              name="access_key"
              value={credentials.access_key}
              onChange={handleChange}
              variant="outlined"
              placeholder="AKIA..."
              required
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Secret Access Key"
              name="secret_key"
              value={credentials.secret_key}
              onChange={handleChange}
              type="password"
              variant="outlined"
              required
            />
          </Grid>
          <Grid item xs={12}>
             <TextField
              fullWidth
              select
              label="Region"
              name="region"
              value={credentials.region}
              onChange={handleChange}
              variant="outlined"
              required
            >
              {COMMON_REGIONS.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
        </Grid>

        <Button 
          variant="contained" 
          color="warning" // AWS themed color roughly
          size="large"
          fullWidth
          disabled={loading}
          onClick={handleConnect}
          sx={{ py: 1.5, borderRadius: 2, mb: 3, bgcolor: '#FF9900', '&:hover': { bgcolor: '#F57C00' } }}
        >
          {loading ? 'Connecting...' : 'Connect AWS Account'}
        </Button>

        {status === 'success' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Alert icon={<CheckCircleOutline fontSize="inherit" />} severity="success" sx={{ borderRadius: 2 }}>
              AWS Account connected successfully! Redirecting...
            </Alert>
          </motion.div>
        )}

        {status === 'error' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Alert icon={<ErrorOutline fontSize="inherit" />} severity="error" sx={{ borderRadius: 2 }}>
              {errorMessage}
            </Alert>
          </motion.div>
        )}
      </Paper>
    </Box>
  );
}
