interface ErrorStateProps {
  file: string;
  target?: string;
}

export function ErrorState({ file, target = 'make loop && make web-data' }: ErrorStateProps) {
  return (
    <div
      className="rounded-stadium border-[1.5px] p-10"
      style={{ borderColor: 'var(--signal-orange)' }}
    >
      <p className="text-subhead uppercase" style={{ color: 'var(--signal-orange)' }}>
        Missing artefact
      </p>
      <p className="mt-3 text-body">
        <code>frontend/data/run/{file}</code> is missing or unreadable.
      </p>
      <p className="mt-2 text-body" style={{ color: 'var(--slate-gray)' }}>
        Regenerate it with <code>{target}</code>.
      </p>
    </div>
  );
}
