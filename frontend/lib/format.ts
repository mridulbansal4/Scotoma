const PERCENT_DIGITS = 1;
const RATE_DIGITS = 3;
const MILLISECOND_DIGITS = 2;

export function percent(value: number | null | undefined, digits = PERCENT_DIGITS): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${(value * 100).toFixed(digits)}%`;
}

export function rate(value: number | null | undefined, digits = RATE_DIGITS): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return value.toFixed(digits);
}

export function milliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return `${value.toFixed(MILLISECOND_DIGITS)} ms`;
}

export function currency(value: number | null | undefined, code = 'USD'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: code,
    maximumFractionDigits: 0,
  }).format(value);
}

export function count(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US').format(value);
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ');
}

/** Interpolates dust taupe to ink black, which is how every heatmap cell is filled. */
export function inkScale(value: number | null): string {
  if (value === null || Number.isNaN(value)) return 'var(--soft-bone)';
  const clamped = Math.max(0, Math.min(1, value));
  const from = [209, 205, 199];
  const to = [20, 20, 19];
  const channels = from.map((start, index) => Math.round(start + (to[index] - start) * clamped));
  return `rgb(${channels.join(', ')})`;
}

export function readableOn(value: number | null): string {
  if (value === null || Number.isNaN(value)) return 'var(--slate-gray)';
  return value > 0.55 ? 'var(--lifted-cream)' : 'var(--ink-black)';
}
