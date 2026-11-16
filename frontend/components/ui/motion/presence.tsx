"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

export type PresenceProps = {
  show: boolean;
  children: ReactNode;
  className?: string;
};

export function Presence({ show, children, className }: PresenceProps) {
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <AnimatePresence initial={false}>
      {show ? (
        <motion.div
          className={className}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.16, ease: "easeOut" }}
        >
          {children}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
