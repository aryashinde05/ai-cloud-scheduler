import React from 'react';
import { Card, CardContent, Typography, Box, Button, Chip, Stack } from '@mui/material';
import { motion } from 'framer-motion';
import { TrendingDown, InfoOutlined, Bolt } from '@mui/icons-material';

interface OpportunityCardProps {
  service: string;
  type: string;
  cost: number;
  savings: number;
  confidence: 'high' | 'medium' | 'low';
  description: string;
  action: string;
  onAction?: () => void;
}

export const OpportunityCard: React.FC<OpportunityCardProps> = ({ 
  service, type, cost, savings, confidence, description, action, onAction 
}) => {
  const getConfidenceColor = () => {
    if (confidence === 'high') return 'success';
    if (confidence === 'medium') return 'warning';
    return 'info';
  };

  return (
    <motion.div whileHover={{ y: -5, transition: { duration: 0.2 } }}>
      <Card sx={{ 
        borderRadius: 4, 
        height: '100%',
        bgcolor: 'background.paper',
        backgroundImage: 'none',
        border: '1px solid rgba(255,255,255,0.05)',
        transition: 'border-color 0.2s',
        '&:hover': {
          borderColor: 'primary.main',
        }
      }}>
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
            <Box>
              <Typography variant="caption" color="primary.main" fontWeight={700} sx={{ textTransform: 'uppercase', letterSpacing: 1 }}>
                {service} • {type.replace('_', ' ')}
              </Typography>
              <Typography variant="h6" fontWeight={700} sx={{ mt: 0.5 }}>
                Save ${savings.toLocaleString()}/mo
              </Typography>
            </Box>
            <Chip 
              label={`${confidence.toUpperCase()} CONFIDENCE`} 
              size="small" 
              color={getConfidenceColor()} 
              variant="outlined"
              sx={{ fontWeight: 700, fontSize: '0.65rem' }}
            />
          </Box>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3, minHeight: 40 }}>
            {description}
          </Typography>
          
          <Box sx={{ p: 2, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.02)', mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Bolt fontSize="small" color="primary" />
              <Typography variant="subtitle2" fontWeight={600}>Recommended Action</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              {action}
            </Typography>
          </Box>

          <Button 
            variant="contained" 
            color="primary" 
            onClick={onAction} 
            fullWidth 
            startIcon={<TrendingDown />}
            sx={{ borderRadius: 2, py: 1, fontWeight: 600 }}
          >
            Implement Optimization
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );
};
