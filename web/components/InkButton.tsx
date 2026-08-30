type Variant = 'primary' | 'secondary';

interface InkButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: Variant;
  disabled?: boolean;
  pressed?: boolean;
  ariaLabel?: string;
}

const BASE = 'rounded-button border-[1.5px] px-6 py-2 text-navlink transition-transform active:scale-[0.98]';

export function InkButton({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  pressed = false,
  ariaLabel,
}: InkButtonProps) {
  const solid = variant === 'primary' || pressed;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={pressed || undefined}
      className={BASE}
      style={{
        background: solid ? 'var(--ink-black)' : 'var(--white)',
        color: solid ? 'var(--canvas-cream)' : 'var(--ink-black)',
        borderColor: 'var(--ink-black)',
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {children}
    </button>
  );
}
