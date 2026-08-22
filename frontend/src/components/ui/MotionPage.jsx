import { motion } from 'framer-motion';

/**
 * Animated page wrapper. Wrap each page's outermost div in
 * <MotionPage> to get a subtle fade + slide-up on mount.
 */
export function MotionPage({ children, className, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1], delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
