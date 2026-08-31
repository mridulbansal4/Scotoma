import type { Metadata } from 'next';
import localFont from 'next/font/local';

import { NavPill } from '@/components/NavPill';
import './globals.css';

// Self-hosted so the no-network rule holds: no font CDN, no runtime request.
const sofia = localFont({
  src: './fonts/SofiaSans-Variable.woff2',
  variable: '--font-sofia',
  display: 'swap',
  weight: '100 1000',
  fallback: ['Arial', 'sans-serif'],
});

export const metadata: Metadata = {
  title: 'Scotoma — Closed-Loop Adversarial Fraud Engine',
  description: 'Offline adversarial testing lab — blind-spot measurement, not a guarantee.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sofia.variable}>
      <body className="min-h-screen bg-[#fafbfc] font-sans antialiased text-[#1e2033] relative selection:bg-[#a5bbfc]/30">
        {/* Sarvam.ai Inspired Top Ambient Glow */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 -z-10 h-[500px] w-full max-w-7xl -translate-x-1/2 opacity-40 blur-[100px]"
          style={{
            background: 'radial-gradient(ellipse at top, #a5bbfc 0%, #d5e2ff 45%, transparent 75%)',
          }}
        />

        <NavPill />
        <main className="pt-24 lg:pt-28 pb-16">{children}</main>

        <footer className="mt-20 border-t border-slate-200/60 bg-[#1e2033] px-6 pb-20 pt-16 text-white lg:px-12 relative overflow-hidden">
          {/* Subtle footer background spotlight */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-20 right-0 h-[300px] w-[500px] opacity-15 blur-[90px]"
            style={{
              background: 'radial-gradient(circle, #a5bbfc 0%, transparent 70%)',
            }}
          />
          <div className="mx-auto max-w-content relative z-10">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
              <div>
                <span className="text-[12px] font-semibold uppercase tracking-widest text-[#a5bbfc]">
                  SCOTOMA ADVERSARIAL ENGINE
                </span>
                <h2 className="mt-2 max-w-2xl text-[26px] md:text-[32px] font-medium leading-tight text-white">
                  It measures and shrinks blind spots. It is not a security guarantee.
                </h2>
              </div>
            </div>
            <div className="mt-10 h-px w-full bg-white/10" />
            <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-300/70">
              <p>
                Scotoma — Offline Adversarial Testing Engine. Every figure is read from committed run artefacts.
              </p>
              <span className="rounded-full bg-white/10 px-3 py-1 text-[11px] font-medium text-white/90">
                Zero Network Calls • Statically Audited
              </span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}

