import { useId, type InputHTMLAttributes, type ReactNode } from 'react';

export function Field({
  label,
  hint,
  error,
  className = '',
  ...input
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: ReactNode; error?: string }) {
  const id = useId();
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="text-sm font-semibold text-ink">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? `${id}-d` : undefined}
        className="h-11 rounded-control border border-linestrong bg-surface px-3 text-base text-ink placeholder:text-ink2/70 focus:border-ward"
        {...input}
      />
      {(error || hint) && (
        <p id={`${id}-d`} className={`text-sm ${error ? 'text-bad-ink' : 'text-ink2'}`}>
          {error || hint}
        </p>
      )}
    </div>
  );
}
