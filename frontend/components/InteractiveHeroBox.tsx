'use client';

import { useMotionValue, useSpring, useMotionTemplate, motion, useReducedMotion } from 'motion/react';
import { useRef, MouseEvent, ReactNode, useState } from 'react';

export function InteractiveHeroBox({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Track raw mouse coordinates
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Snappy spring tracking for immediate natural spotlight movement (Apple Design spec)
  const springConfig = { bounce: 0, duration: 0.3 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  const shouldReduceMotion = useReducedMotion();

  const [isHovered, setIsHovered] = useState(false);

  function handleMouseEnter(e: MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Immediately snap initial position to mouse enter point so spotlight doesn't slide from (0,0)
    if (typeof mouseX.jump === 'function') {
      mouseX.jump(x);
      mouseY.jump(y);
    } else {
      mouseX.set(x);
      mouseY.set(y);
    }
    setIsHovered(true);
  }

  function handleMouseMove(e: MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    mouseX.set(e.clientX - rect.left);
    mouseY.set(e.clientY - rect.top);
    if (!isHovered) {
      setIsHovered(true);
    }
  }

  function handleMouseLeave() {
    setIsHovered(false);
  }

  // Construct crisp, dark, highly visible radial gradient with a focused spotlight radius
  const background = useMotionTemplate`radial-gradient(
    280px circle at ${smoothX}px ${smoothY}px,
    rgba(30, 45, 110, 0.38),
    rgba(30, 45, 110, 0.15) 42%,
    transparent 75%
  )`;

  return (
    <div
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`group relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-50/90 via-blue-50/40 to-white/95 border border-indigo-200/80 p-6 lg:p-8 shadow-sm sarvam-mesh-texture cursor-default touch-none ${className}`}
    >
      {/* Static top-right ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-20 -right-20 h-80 w-80 rounded-full bg-gradient-to-br from-indigo-300/30 via-blue-200/20 to-transparent blur-3xl"
      />

      {/* The instant cursor-following spotlight overlay, disabled for reduced motion */}
      {!shouldReduceMotion && (
        <motion.div
          className="pointer-events-none absolute inset-0 z-0 transition-opacity duration-150"
          style={{
            background,
            opacity: isHovered ? 1 : 0,
          }}
        />
      )}

      <div className="flex flex-col items-start max-w-4xl relative z-10">
        {children}
      </div>
    </div>
  );
}