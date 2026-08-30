import type { Config } from 'tailwindcss';

// Every value here mirrors a CSS custom property declared in app/globals.css. No component
// hard-codes a hex value; the two files are the single token surface.
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--canvas-cream)',
        lifted: 'var(--lifted-cream)',
        white: 'var(--white)',
        bone: 'var(--soft-bone)',
        ink: 'var(--ink-black)',
        charcoal: 'var(--charcoal)',
        slate: 'var(--slate-gray)',
        dust: 'var(--dust-taupe)',
        ghost: 'var(--ghost-cream)',
        signal: 'var(--signal-orange)',
        'signal-light': 'var(--light-signal-orange)',
        clay: 'var(--clay-brown)',
        link: 'var(--link-blue)',
        'mc-red': 'var(--mc-red)',
        'mc-yellow': 'var(--mc-yellow)',
      },
      borderRadius: {
        button: 'var(--radius-button)',
        consent: 'var(--radius-consent)',
        stadium: 'var(--radius-stadium)',
        pill: 'var(--radius-pill)',
      },
      boxShadow: {
        lift: 'var(--shadow-1)',
        card: 'var(--shadow-2)',
      },
      spacing: {
        unit: 'var(--space-unit)',
      },
      maxWidth: {
        content: 'var(--content-max)',
      },
      fontFamily: {
        sans: ['var(--font-sofia)', 'SofiaSans', 'Arial', 'sans-serif'],
      },
      fontSize: {
        hero: ['64px', { lineHeight: '64px', letterSpacing: '-1.28px', fontWeight: '500' }],
        section: ['36px', { lineHeight: '44px', letterSpacing: '-0.72px', fontWeight: '500' }],
        card: ['24px', { lineHeight: '28.8px', letterSpacing: '-0.48px', fontWeight: '500' }],
        subhead: ['14px', { lineHeight: '18.2px', fontWeight: '700' }],
        eyebrow: ['14px', { lineHeight: '14px', letterSpacing: '0.56px', fontWeight: '700' }],
        body: ['16px', { lineHeight: '22.4px' }],
        navlink: ['16px', { lineHeight: '16px', letterSpacing: '-0.48px', fontWeight: '500' }],
        data: ['13px', { lineHeight: '16px' }],
        readout: ['36px', { lineHeight: '40px', letterSpacing: '-0.72px', fontWeight: '500' }],
      },
    },
  },
  plugins: [],
};

export default config;
