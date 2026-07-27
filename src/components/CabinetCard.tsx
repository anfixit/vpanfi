import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function CabinetCard({
  title,
  icon,
  children,
  className = "",
}: {
  title: string;
  icon: IconName;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article className={`cabinet-card ${className}`.trim()}>
      <header>
        <span className="cabinet-card-icon">
          <Icon name={icon} />
        </span>
        <h3>{title}</h3>
      </header>
      {children}
    </article>
  );
}
