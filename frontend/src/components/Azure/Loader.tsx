import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { motion } from 'framer-motion';

export const Loader: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => {
  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      p: 10,
      minHeight: 300
    }}>
      <motion.div
        animate={{
          scale: [1, 1.1, 1],
          rotate: [0, 360],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      >
        <CircularProgress size={48} thickness={4} sx={{ color: 'primary.main' }} />
      </motion.div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <Typography variant="body1" sx={{ mt: 3, color: 'text.secondary', fontWeight: 500, letterSpacing: 0.5 }}>
          {message}
        </Typography>
      </motion.div>
    </Box>
  );
};
