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
  title: 'Scotoma',
  description: 'Closed-loop adversarial fraud engine — blind-spot measurement, not a guarantee.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sofia.variable}>
      <body className="min-h-screen bg-canvas font-sans antialiased">
        <NavPill />
        <main className="pt-28 lg:pt-32">{children}</main>
        <footer className="mt-24 bg-ink px-6 pb-24 pt-16 text-white lg:px-12">
          <div className="mx-auto max-w-content">
            <h2 className="max-w-2xl text-section">
              It measures and shrinks blind spots. It is not a security guarantee.
            </h2>
            <div className="mt-12 h-px w-full bg-white/30" />
            <p className="mt-6 text-data text-white/70">
              Scotoma — offline adversarial testing lab. Every figure on these screens is read from
              committed run artefacts. Nothing on this site makes a network call.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
