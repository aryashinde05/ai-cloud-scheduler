import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';
import { motion } from 'framer-motion';

interface CostCardProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;
  subtitle?: React.ReactNode;
}

export const CostCard: React.FC<CostCardProps> = ({ title, value, icon, subtitle }) => {
  return (
    <motion.div whileHover={{ y: -5, transition: { duration: 0.2 } }}>
      <Card sx={{ 
        borderRadius: 4, 
        bgcolor: 'background.paper',
        backgroundImage: 'none',
        border: '1px solid rgba(255,255,255,0.05)',
        height: '100%',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Subtle background glow */}
        <Box sx={{ 
          position: 'absolute', top: -40, right: -40, 
          width: 100, height: 100, borderRadius: '50%', 
          bgcolor: 'primary.main', opacity: 0.05, filter: 'blur(40px)' 
        }} />
        
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', letterSpacing: 1 }}>
              {title}
            </Typography>
            {icon && <Box sx={{ color: 'primary.main', opacity: 0.8 }}>{icon}</Box>}
          </Box>
          <Typography variant="h3" component="div" sx={{ fontWeight: 800, mb: 1.5, letterSpacing: -1 }}>
            {value}
          </Typography>
          {subtitle && (
            <Box sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
              {subtitle}
            </Box>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};
