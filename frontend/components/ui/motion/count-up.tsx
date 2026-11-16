"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

export type CountUpProps = {
  value: number;
  format?: (value: number) => string;
  duration?: number;
  className?: string;
};

export function CountUp({
  value,
  format = (current) => String(current),
  duration = 0.8,
  className,
}: CountUpProps) {
  const reduceMotion = useReducedMotion() ?? false;
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (reduceMotion) {
      return;
    }

    const controls = animate(0, value, {
      duration,
      ease: "easeOut",
      onUpdate: (latest) => setDisplay(Math.round(latest)),
    });

    return () => controls.stop();
  }, [duration, reduceMotion, value]);

  return (
    <span className={className}>
      <span aria-hidden="true" className="motion-safe:inline motion-reduce:hidden">
        {format(display)}
      </span>
      <span aria-hidden="true" className="hidden motion-reduce:inline">
        {format(value)}
      </span>
      <span className="sr-only">{format(value)}</span>
    </span>
  );
}
