export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-stadium border border-dust/60 p-10 text-center">
      <p className="text-body" style={{ color: 'var(--dust-taupe)' }}>
        {message}
      </p>
    </div>
  );
}
