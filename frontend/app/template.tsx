'use client';

import { motion } from 'motion/react';
import { ReactNode } from 'react';

export default function Template({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.99 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
}
