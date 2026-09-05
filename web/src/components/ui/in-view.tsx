import React, { useRef } from 'react';
import { motion, useInView, type Transition, type Variant } from 'motion/react';

interface InViewProps {
  children: React.ReactNode;
  variants?: { hidden: Variant; visible: Variant };
  transition?: Transition;
  className?: string;
  viewOptions?: Parameters<typeof useInView>[1];
}

export const InView: React.FC<InViewProps> = ({
  children,
  variants = {
    hidden: { opacity: 0, y: 16, filter: 'blur(4px)' },
    visible: { opacity: 1, y: 0, filter: 'blur(0px)' },
  },
  transition = { duration: 0.5, ease: [0.21, 0.47, 0.32, 0.98] },
  className = '',
  viewOptions = { once: true, margin: '-40px' },
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, viewOptions);

  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={isInView ? 'visible' : 'hidden'}
      variants={variants}
      transition={transition}
      className={className}
    >
      {children}
    </motion.div>
  );
};
