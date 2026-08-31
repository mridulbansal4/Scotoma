'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X, ShieldAlert } from 'lucide-react';
import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ScotomaMark } from './ScotomaMark';

const LINKS = [
  { href: '/atlas', label: 'Attack Atlas' },
  { href: '/redteam', label: 'Red Team' },
  { href: '/fidelity', label: 'Fidelity Lab' },
  { href: '/soc', label: 'Blue Team' },
  { href: '/loop', label: 'The Loop' },
];

const ICON_SIZE = 18;

export function NavPill() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="fixed inset-x-0 top-0 z-50 pt-4 px-4 lg:px-8 pointer-events-none transform-gpu">
      <nav className="pointer-events-auto mx-auto flex max-w-content items-center justify-between rounded-full bg-white/60 backdrop-blur-2xl backdrop-saturate-[1.8] border-t border-white/40 px-4 py-2.5 shadow-[0_4px_25px_-5px_rgba(30,32,51,0.08),0_0_0_1px_rgba(30,32,51,0.08)] lg:px-8 lg:py-3 transition-all duration-200 transform-gpu">
        <Link
          href="/atlas"
          prefetch={true}
          className="flex items-center gap-3 text-ink group"
          aria-label="Scotoma home"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#1e2033] text-white shadow-sm transition-transform duration-200 group-hover:scale-105 active:scale-95 transform-gpu">
            <ScotomaMark size={20} />
          </div>
          <div className="flex flex-col">
            <span className="text-[16px] font-semibold tracking-tight text-[#1e2033] leading-none">
              Scotoma
            </span>
            <span className="text-[11px] font-medium text-slate tracking-wide">
              ADVERSARIAL ENGINE
            </span>
          </div>
        </Link>

        {/* Desktop Navigation Links with instant hardware-accelerated active pill */}
        <div className="hidden items-center gap-1.5 lg:flex bg-[#f4f5fa] p-1 rounded-full border border-slate-200/50">
          {LINKS.map((link) => {
            const isActive = pathname === link.href || (link.href !== '/' && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                prefetch={true}
                className={`relative px-4 py-1.5 text-[14px] font-medium rounded-full transition-all duration-150 transform-gpu active:scale-[0.97] ${
                  isActive
                    ? 'bg-[#1e2033] text-white shadow-sm font-semibold'
                    : 'text-slate hover:text-ink hover:bg-white/70'
                }`}
              >
                <span className="relative z-10">{link.label}</span>
              </Link>
            );
          })}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <Link
            href="/soc"
            prefetch={true}
            className="hidden sm:inline-flex items-center gap-2 rounded-full bg-gradient-to-b from-[#3a3f5c] to-[#1e2033] px-4 py-1.5 text-[13px] font-medium text-white shadow-sm transition-all duration-150 hover:shadow-md active:scale-[0.97] transform-gpu"
          >
            <ShieldAlert size={14} className="text-[#a5bbfc]" />
            <span>SOC Console</span>
          </Link>

          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f4f5fa] text-[#1e2033] border border-slate-200/60 lg:hidden transition-transform duration-150 active:scale-90 transform-gpu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
          >
            {open ? <X size={ICON_SIZE} /> : <Menu size={ICON_SIZE} />}
          </button>
        </div>
      </nav>

      {/* Mobile Drawer Menu */}
      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
            className="pointer-events-auto mx-auto mt-2 max-w-content rounded-2xl bg-white/70 backdrop-blur-2xl backdrop-saturate-[1.8] border-t border-white/40 p-5 shadow-2xl lg:hidden origin-top"
          >
            <ul className="flex flex-col gap-2">
              {LINKS.map((link) => {
                const isActive = pathname === link.href || (link.href !== '/' && pathname.startsWith(link.href));
                return (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      prefetch={true}
                      className={`block px-4 py-2.5 text-[15px] font-medium rounded-xl transition-all duration-150 active:scale-[0.97] ${
                        isActive ? 'bg-[#1e2033] text-white font-semibold' : 'text-slate hover:bg-[#f4f5fa]'
                      }`}
                      onClick={() => setOpen(false)}
                    >
                      {link.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
