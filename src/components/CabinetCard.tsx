import type { ReactNode } from "react";

export function CabinetCard({
  title,
  icon,
  children,
  className = "",
}: {
  title: string;
  icon: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article className={`cabinet-card ${className}`.trim()}>
      <header>
        <span aria-hidden="true">{icon}</span>
        <h3>{title}</h3>
      </header>
      {children}
    </article>
  );
}
