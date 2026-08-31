'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowUpRight } from 'lucide-react';

interface StatPortraitProps {
  value: string;
  label: string;
  caption: string;
  satellite?: boolean;
  href?: string;
}

const SATELLITE_SIZE = 48;
const ICON_SIZE = 18;

// A small hook to count up numbers for an awesome loading effect
function useCountUp(endValue: string, duration: number = 1500) {
  const [displayValue, setDisplayValue] = useState('0');

  useEffect(() => {
    // If it's not a number or percentage, just show it
    const isPercent = endValue.includes('%');
    const numericPart = endValue.replace(/[^0-9.]/g, '');
    const num = parseFloat(numericPart);

    if (isNaN(num)) {
      setDisplayValue(endValue);
      return;
    }

    let start = 0;
    const incrementTime = 30;
    const steps = duration / incrementTime;
    const increment = num / steps;

    const timer = setInterval(() => {
      start += increment;
      if (start >= num) {
        clearInterval(timer);
        setDisplayValue(endValue);
      } else {
        // preserve decimal places if original had them
        const decimals = endValue.includes('.') ? endValue.split('.')[1].length : 0;
        const formatted = start.toFixed(decimals);
        setDisplayValue(isPercent ? `${formatted}%` : formatted);
      }
    }, incrementTime);

    return () => clearInterval(timer);
  }, [endValue, duration]);

  return displayValue;
}

export function StatPortrait({ value, label, caption, satellite = true, href }: StatPortraitProps) {
  const animatedValue = useCountUp(value, 2000);

  return (
    <figure className="group flex flex-col items-center text-center">
      <div className="relative">
        {/* Animated Crazy 3D Ring */}
        <div className="scotoma-stat-ring flex h-[160px] w-[160px] lg:h-[180px] lg:w-[180px] rounded-full transition-transform duration-500 group-hover:scale-105">
          <div className="scotoma-stat-inner flex flex-col justify-center items-center">
            <span className="text-[36px] lg:text-[44px] font-medium tracking-tight text-[#1e2033] tabular-nums z-10 drop-shadow-sm">
              {animatedValue}
            </span>
          </div>
        </div>

        {satellite ? (
          href ? (
            <Link
              href={href}
              className="absolute bottom-0 right-0 flex items-center justify-center rounded-full bg-[#1e2033] text-white shadow-lg transition-transform duration-500 group-hover:scale-110 group-hover:rotate-12 group-hover:shadow-[#1e2033]/40 z-20"
              style={{ width: SATELLITE_SIZE, height: SATELLITE_SIZE, boxShadow: '0 8px 16px rgba(30,32,51,0.3)' }}
              aria-label={`Go to ${label}`}
            >
              <ArrowUpRight size={ICON_SIZE} className="text-white" />
            </Link>
          ) : (
            <span
              className="absolute bottom-0 right-0 flex items-center justify-center rounded-full bg-[#1e2033] text-white shadow-lg transition-transform duration-500 group-hover:scale-110 group-hover:rotate-12 group-hover:shadow-[#1e2033]/40 z-20"
              style={{ width: SATELLITE_SIZE, height: SATELLITE_SIZE, boxShadow: '0 8px 16px rgba(30,32,51,0.3)' }}
              aria-hidden
            >
              <ArrowUpRight size={ICON_SIZE} className="text-white" />
            </span>
          )
        ) : null}
      </div>

      <figcaption className="mt-6 max-w-[260px] animate-fade-in-up" style={{ animationDelay: '0.2s', opacity: 0, animationFillMode: 'forwards' }}>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#1e2033]/80">
          {label}
        </p>
        <p className="mt-1.5 text-[14px] leading-relaxed text-slate-500">{caption}</p>
      </figcaption>
    </figure>
  );
}
