import { cn } from '../../utils/cn.js';

/**
 * Polished page header — eyebrow + title + subtitle + actions.
 * Used at the top of every authenticated page. The eyebrow is a
 * small uppercase label that gives the page a sense of place inside
 * the product (e.g. "WORKSPACE", "DRAFTS").
 */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  description,
  actions,
  className,
}) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between',
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow ? (
          <div className="label-faint mb-2">{eyebrow}</div>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-1 text-sm text-text-secondary sm:text-base">
            {subtitle}
          </p>
        ) : null}
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
