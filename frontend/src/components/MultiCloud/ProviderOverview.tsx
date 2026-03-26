/**
 * Provider Overview Component
 * 
 * Displays overview information for a cloud provider including
 * supported regions, services, and pricing model.
 */

import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Avatar,
  Tooltip,
  LinearProgress
} from '@mui/material';
import {
  Cloud as AWSIcon,
  Google as GoogleIcon,
  Microsoft as MicrosoftIcon,
  Cloud as CloudIcon
} from '@mui/icons-material';

import { CloudProvider } from '../../services/multiCloudApi';

interface ProviderOverviewProps {
  provider: CloudProvider;
}

const ProviderOverview: React.FC<ProviderOverviewProps> = ({ provider }) => {
  const getProviderIcon = (providerType: string) => {
    switch (providerType.toLowerCase()) {
      case 'aws':
        return <AWSIcon sx={{ color: '#FF9900' }} />;
      case 'gcp':
        return <GoogleIcon sx={{ color: '#4285F4' }} />;
      case 'azure':
        return <MicrosoftIcon sx={{ color: '#0078D4' }} />;
      default:
        return <CloudIcon />;
    }
  };

  const getProviderColor = (providerType: string) => {
    switch (providerType.toLowerCase()) {
      case 'aws':
        return '#FF9900';
      case 'gcp':
        return '#4285F4';
      case 'azure':
        return '#0078D4';
      default:
        return '#666';
    }
  };

  const getProviderStats = (provider: CloudProvider) => {
    // Check if the provider object already has stats (e.g. from expanded API)
    if (provider.pricing_model?.includes('{')) {
       try {
         const parsed = JSON.parse(provider.pricing_model);
         if (parsed.marketShare) return parsed;
       } catch (e) {}
    }

    // Mock stats fallback
    const stats = {
      aws: { marketShare: 32, reliability: 99.9, avgCost: 'Medium' },
      gcp: { marketShare: 9, reliability: 99.8, avgCost: 'Low' },
      azure: { marketShare: 20, reliability: 99.9, avgCost: 'Medium-High' }
    };
    return stats[provider.provider_type.toLowerCase() as keyof typeof stats] || 
           { marketShare: 0, reliability: 99.0, avgCost: 'Unknown' };
  };

  const stats = getProviderStats(provider);

  return (
    <Card 
      sx={{ 
        height: '100%',
        border: `2px solid ${getProviderColor(provider.provider_type)}20`,
        '&:hover': {
          border: `2px solid ${getProviderColor(provider.provider_type)}40`,
          transform: 'translateY(-2px)',
          transition: 'all 0.2s ease-in-out'
        }
      }}
    >
      <CardContent>
        {/* Provider Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Avatar 
            sx={{ 
              bgcolor: `${getProviderColor(provider.provider_type)}20`,
              mr: 2,
              width: 48,
              height: 48
            }}
          >
            {getProviderIcon(provider.provider_type)}
          </Avatar>
          <Box>
            <Typography variant="h6" component="h3">
              {provider.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {provider.pricing_model}
            </Typography>
          </Box>
        </Box>

        {/* Stats */}
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Market Share
            </Typography>
            <Typography variant="body2" fontWeight="medium">
              {stats.marketShare}%
            </Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={stats.marketShare} 
            sx={{ 
              height: 6, 
              borderRadius: 3,
              backgroundColor: `${getProviderColor(provider.provider_type)}20`,
              '& .MuiLinearProgress-bar': {
                backgroundColor: getProviderColor(provider.provider_type)
              }
            }}
          />
        </Box>

        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Reliability
            </Typography>
            <Typography variant="body2" fontWeight="medium">
              {stats.reliability}%
            </Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={stats.reliability} 
            sx={{ 
              height: 6, 
              borderRadius: 3,
              backgroundColor: `${getProviderColor(provider.provider_type)}20`,
              '& .MuiLinearProgress-bar': {
                backgroundColor: getProviderColor(provider.provider_type)
              }
            }}
          />
        </Box>

        {/* Regions */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Regions ({provider.supported_regions.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {provider.supported_regions.slice(0, 4).map((region) => (
              <Chip
                key={region}
                label={region}
                size="small"
                variant="outlined"
                sx={{ 
                  fontSize: '0.7rem',
                  height: 24,
                  borderColor: `${getProviderColor(provider.provider_type)}40`
                }}
              />
            ))}
            {provider.supported_regions.length > 4 && (
              <Tooltip 
                title={provider.supported_regions.slice(4).join(', ')}
                arrow
              >
                <Chip
                  label={`+${provider.supported_regions.length - 4}`}
                  size="small"
                  variant="filled"
                  sx={{ 
                    fontSize: '0.7rem',
                    height: 24,
                    backgroundColor: `${getProviderColor(provider.provider_type)}20`,
                    color: getProviderColor(provider.provider_type)
                  }}
                />
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Services */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Services ({provider.supported_services.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {provider.supported_services.slice(0, 3).map((service) => (
              <Chip
                key={service}
                label={service}
                size="small"
                variant="outlined"
                sx={{ 
                  fontSize: '0.7rem',
                  height: 24,
                  borderColor: `${getProviderColor(provider.provider_type)}40`
                }}
              />
            ))}
            {provider.supported_services.length > 3 && (
              <Tooltip 
                title={provider.supported_services.slice(3).join(', ')}
                arrow
              >
                <Chip
                  label={`+${provider.supported_services.length - 3}`}
                  size="small"
                  variant="filled"
                  sx={{ 
                    fontSize: '0.7rem',
                    height: 24,
                    backgroundColor: `${getProviderColor(provider.provider_type)}20`,
                    color: getProviderColor(provider.provider_type)
                  }}
                />
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Cost Level */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Avg. Cost Level
          </Typography>
          <Chip
            label={stats.avgCost}
            size="small"
            sx={{
              backgroundColor: `${getProviderColor(provider.provider_type)}20`,
              color: getProviderColor(provider.provider_type),
              fontWeight: 'medium'
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
};

export default ProviderOverview;