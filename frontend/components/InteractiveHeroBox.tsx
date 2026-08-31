'use client';

import { useMotionValue, useSpring, useMotionTemplate, motion } from 'motion/react';
import { useRef, MouseEvent, ReactNode } from 'react';

export function InteractiveHeroBox({ children }: { children: ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Track raw mouse coordinates
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  
  // Apply spring physics for that smooth, laggy premium feel
  const smoothX = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const smoothY = useSpring(mouseY, { stiffness: 50, damping: 20 });

  // Optional: fade the gradient in/out on enter/leave
  const opacity = useSpring(0, { stiffness: 60, damping: 20 });

  function handleMouseMove(e: MouseEvent<HTMLDivElement>) {
    const { left, top } = e.currentTarget.getBoundingClientRect();
    mouseX.set(e.clientX - left);
    mouseY.set(e.clientY - top);
  }

  // Construct the CSS radial gradient using the smoothed coordinates
  // Darkened as requested for better visibility
  const background = useMotionTemplate`radial-gradient(
    450px circle at ${smoothX}px ${smoothY}px,
    rgba(35, 55, 130, 0.28),
    rgba(35, 55, 130, 0.12) 45%,
    transparent 80%
  )`;

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => opacity.set(1)}
      onMouseLeave={() => opacity.set(0)}
      className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-50/90 via-blue-50/40 to-white/95 border border-indigo-200/80 p-6 lg:p-8 shadow-sm sarvam-mesh-texture cursor-default touch-none"
    >
      {/* Existing static top-right ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-20 -right-20 h-80 w-80 rounded-full bg-gradient-to-br from-indigo-300/30 via-blue-200/20 to-transparent blur-3xl"
      />

      {/* The animated cursor-following spotlight overlay */}
      <motion.div
        className="pointer-events-none absolute inset-0 z-0 transition-opacity duration-500"
        style={{ background, opacity }}
      />

      <div className="flex flex-col items-start max-w-4xl relative z-10">
        {children}
      </div>
    </div>
  );
}