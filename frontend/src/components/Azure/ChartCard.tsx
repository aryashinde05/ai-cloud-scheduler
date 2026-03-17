import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
}

export const ChartCard: React.FC<ChartCardProps> = ({ title, children }) => {
  return (
    <Card sx={{ borderRadius: 4, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', height: '100%' }}>
      <CardContent sx={{ p: 3, pt: 2 }}>
        <Typography variant="h6" fontWeight={600} mb={3}>
          {title}
        </Typography>
        <Box sx={{ height: 300, width: '100%' }}>
          {children}
        </Box>
      </CardContent>
    </Card>
  );
};
