const DOT_SIZE = 6;

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-eyebrow uppercase">
      <span
        className="inline-block rounded-pill bg-signal-light"
        style={{ width: DOT_SIZE, height: DOT_SIZE }}
        aria-hidden
      />
      {children}
    </p>
  );
}
