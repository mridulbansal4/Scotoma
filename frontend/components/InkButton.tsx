'use client';

import React, { useState, useRef } from 'react';

type Variant = 'primary' | 'secondary';

interface InkButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: Variant;
  disabled?: boolean;
  pressed?: boolean;
  ariaLabel?: string;
  className?: string;
}

export function InkButton({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  pressed = false,
  ariaLabel,
  className = '',
}: InkButtonProps) {
  const solid = variant === 'primary' || pressed;
  const btnRef = useRef<HTMLButtonElement>(null);
  const [mousePos, setMousePos] = useState({ x: 50, y: 50 });

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setMousePos({ x, y });
  };

  return (
    <button
      ref={btnRef}
      type="button"
      onClick={onClick}
      onMouseMove={handleMouseMove}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={pressed || undefined}
      className={`group relative inline-flex items-center justify-center font-medium rounded-pill touch-manipulation overflow-hidden min-h-[40px] px-6 py-2.5 text-[15px] transition-all duration-300 ease-[cubic-bezier(0.2,0,0,1)] active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none ${className}`}
      style={{
        background: solid
          ? 'linear-gradient(to bottom, #3a3f5c 0%, #1e2033 100%)'
          : 'linear-gradient(to bottom, #ffffff 0%, #f0f1f5 100%)',
        color: solid ? '#ffffff' : '#1e2033',
        boxShadow: solid
          ? 'inset 0 1px 0 rgba(255,255,255,0.3), inset 0 -2px 0 rgba(0,0,0,0.25), 0 2px 8px rgba(30,32,51,0.15)'
          : 'inset 0 0 0 1px rgba(30,32,51,0.14), 0 2px 6px rgba(0,0,0,0.03)',
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {/* Sarvam.ai signature radial spotlight follow effect */}
      <span
        aria-hidden="true"
        className="absolute inset-0 rounded-pill pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300 ease-out"
        style={{
          background: `radial-gradient(circle 90px at ${mousePos.x}% ${mousePos.y}%, ${
            solid ? 'rgba(255, 255, 255, 0.2)' : 'rgba(106, 136, 226, 0.15)'
          } 0%, transparent 100%)`,
        }}
      />
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </button>
  );
}

