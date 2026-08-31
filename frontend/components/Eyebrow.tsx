export function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="inline-flex items-center gap-2.5 mb-2">
      <div className="h-px w-6 bg-gradient-to-r from-transparent to-[#6a88e2]" aria-hidden="true" />
      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f0f2f7] px-3.5 py-1 text-[12px] font-semibold uppercase tracking-widest text-[#1e2033] border border-slate-200/60 shadow-2xs">
        <span className="h-1.5 w-1.5 rounded-full bg-[#6a88e2] animate-pulse" aria-hidden="true" />
        {children}
      </span>
      <div className="h-px w-6 bg-gradient-to-l from-transparent to-[#6a88e2]" aria-hidden="true" />
    </div>
  );
}

