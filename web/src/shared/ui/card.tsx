import type { HTMLAttributes, ReactNode } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`card ${className}`} {...props} />;
}

/** Card section title: icon tile, heading and optional trailing content. */
export function CardHeader({
  icon,
  title,
  id,
  description,
  trailing,
  className = "",
}: {
  icon?: ReactNode;
  title: ReactNode;
  id?: string;
  description?: ReactNode;
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`mb-4 flex items-start gap-3 ${className}`}>
      {icon && (
        <span className="bg-brand-soft text-brand-text ring-brand/10 flex size-9 shrink-0 items-center justify-center rounded-lg ring-1">
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <h2 id={id} className="text-ink text-[15px] font-semibold tracking-[-0.01em]">
          {title}
        </h2>
        {description && <p className="text-ink-3 mt-0.5 text-sm">{description}</p>}
      </div>
      {trailing}
    </div>
  );
}
