import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, CardActionArea,
  Button, Chip, Paper,
} from '@mui/material';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Cloud, Storage } from '@mui/icons-material';
import { awsService } from '../services/awsService';

type Provider = 'aws' | 'azure' | null;

const ProviderCard: React.FC<{
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  connected: boolean;
  onSelect: () => void;
  onConnect: () => void;
}> = ({ title, description, icon, color, connected, onSelect, onConnect }) => (
  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
    <Card
      sx={{
        border: `1px solid ${color}40`,
        background: `linear-gradient(135deg, #1a1d3a 0%, #2a2d5a 100%)`,
        '&:hover': { border: `1px solid ${color}99`, boxShadow: `0 0 24px ${color}22` },
        transition: 'all 0.2s',
        height: '100%',
      }}
    >
      <CardContent sx={{ p: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Box sx={{ color, fontSize: 48 }}>{icon}</Box>
          <Box>
            <Typography variant="h5" fontWeight={700}>{title}</Typography>
            {connected && (
              <Chip label="Connected" size="small" sx={{ bgcolor: 'rgba(76,175,80,0.15)', color: '#4caf50', mt: 0.5 }} />
            )}
          </Box>
        </Box>

        <Typography color="text.secondary" sx={{ mb: 4, lineHeight: 1.7 }}>
          {description}
        </Typography>

        <Box sx={{ display: 'flex', gap: 2 }}>
          {connected ? (
            <Button
              variant="contained"
              fullWidth
              onClick={onSelect}
              sx={{ bgcolor: color, '&:hover': { bgcolor: color, filter: 'brightness(0.85)' } }}
            >
              View Dashboard
            </Button>
          ) : (
            <>
              <Button variant="outlined" fullWidth onClick={onConnect}
                sx={{ borderColor: color, color, '&:hover': { borderColor: color, bgcolor: `${color}11` } }}>
                Connect
              </Button>
              <Button variant="contained" fullWidth onClick={onSelect}
                sx={{ bgcolor: color, '&:hover': { bgcolor: color, filter: 'brightness(0.85)' } }}>
                View Demo
              </Button>
            </>
          )}
        </Box>
      </CardContent>
    </Card>
  </motion.div>
);

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [awsConnected, setAwsConnected] = useState(false);
  const [azureConnected, setAzureConnected] = useState(false);

  useEffect(() => {
    // Check AWS connection status
    awsService.getStatus().then(s => setAwsConnected(s.connected));
    // Check Azure — stored in localStorage by AzureConnection page
    setAzureConnected(!!localStorage.getItem('azure_credentials'));
  }, []);

  return (
    <Box>
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <Box sx={{ mb: 6, textAlign: 'center' }}>
          <Typography variant="h3" fontWeight={700} sx={{ mb: 1 }}>
            Cloud Dashboard
          </Typography>
          <Typography color="text.secondary" variant="h6" fontWeight={400}>
            Select your cloud provider to view cost insights and optimization
          </Typography>
        </Box>
      </motion.div>

      <Grid container spacing={4} justifyContent="center" sx={{ maxWidth: 900, mx: 'auto' }}>
        <Grid item xs={12} md={6}>
          <ProviderCard
            title="Amazon Web Services"
            description="Monitor EC2, S3, RDS and all AWS services. Get cost breakdowns, resource optimization recommendations, and budget alerts for your AWS infrastructure."
            icon={<Storage sx={{ fontSize: 48 }} />}
            color="#ff9800"
            connected={awsConnected}
            onSelect={() => navigate('/aws/dashboard')}
            onConnect={() => navigate('/onboarding')}
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <ProviderCard
            title="Microsoft Azure"
            description="Track Azure compute, storage, and networking costs. Identify savings opportunities, analyze service breakdowns, and optimize your Azure spending."
            icon={<Cloud sx={{ fontSize: 48 }} />}
            color="#2196f3"
            connected={azureConnected}
            onSelect={() => navigate('/azure/dashboard')}
            onConnect={() => navigate('/azure/connection')}
          />
        </Grid>
      </Grid>

      {/* Quick stats row if either is connected */}
      {(awsConnected || azureConnected) && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
          <Paper sx={{ mt: 6, p: 3, maxWidth: 900, mx: 'auto', bgcolor: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
              CONNECTED PROVIDERS
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {awsConnected && (
                <Chip
                  icon={<Storage sx={{ color: '#ff9800 !important' }} />}
                  label="AWS Connected"
                  onClick={() => navigate('/aws/dashboard')}
                  sx={{ bgcolor: 'rgba(255,152,0,0.1)', color: '#ff9800', border: '1px solid rgba(255,152,0,0.3)', cursor: 'pointer' }}
                />
              )}
              {azureConnected && (
                <Chip
                  icon={<Cloud sx={{ color: '#2196f3 !important' }} />}
                  label="Azure Connected"
                  onClick={() => navigate('/azure/dashboard')}
                  sx={{ bgcolor: 'rgba(33,150,243,0.1)', color: '#2196f3', border: '1px solid rgba(33,150,243,0.3)', cursor: 'pointer' }}
                />
              )}
            </Box>
          </Paper>
        </motion.div>
      )}
    </Box>
  );
};

export default Dashboard;
