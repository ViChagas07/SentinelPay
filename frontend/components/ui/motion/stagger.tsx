"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const containerVariants = {
  hidden: {},
  show: (stagger: number) => ({
    transition: {
      staggerChildren: stagger,
    },
  }),
};

const itemVariants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0 },
} as const;

export type StaggerProps = {
  children: ReactNode;
  className?: string;
};

export function Stagger({ children, className }: StaggerProps) {
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      custom={reduceMotion ? 0 : 0.04}
      variants={containerVariants}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: StaggerProps) {
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <motion.div
      className={className}
      variants={itemVariants}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.18, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
