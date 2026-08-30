'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, Search, X } from 'lucide-react';
import { useState } from 'react';
import { ScotomaMark } from './ScotomaMark';

const LINKS = [
  { href: '/atlas', label: 'Attack Atlas' },
  { href: '/redteam', label: 'Red Team' },
  { href: '/fidelity', label: 'Fidelity Lab' },
  { href: '/soc', label: 'Blue Team' },
  { href: '/loop', label: 'The Loop' },
];

const ICON_SIZE = 20;

export function NavPill() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed inset-x-0 top-6 z-50 px-4 lg:px-12">
      <nav className="mx-auto flex max-w-content items-center justify-between rounded-pill bg-white px-5 py-3 shadow-lift lg:px-10 lg:py-4">
        <Link href="/atlas" className="flex items-center gap-3 text-ink" aria-label="Scotoma home">
          <ScotomaMark size={26} />
          <span className="text-navlink font-medium">Scotoma</span>
        </Link>

        <div className="hidden items-center gap-12 lg:flex">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-navlink"
              style={{ color: pathname === link.href ? 'var(--ink-black)' : 'var(--slate-gray)' }}
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="hidden h-12 w-12 items-center justify-center rounded-pill border border-ink/20 lg:flex">
            <Search size={ICON_SIZE} aria-hidden />
          </span>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="flex h-12 w-12 items-center justify-center rounded-pill border border-ink/20 lg:hidden"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
          >
            {open ? <X size={ICON_SIZE} /> : <Menu size={ICON_SIZE} />}
          </button>
        </div>
      </nav>

      {open ? (
        <div className="mx-auto mt-3 max-w-content rounded-stadium bg-white p-6 shadow-card lg:hidden">
          <ul className="flex flex-col gap-4">
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="text-navlink" onClick={() => setOpen(false)}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
