import { cn } from '../../utils/cn.js';

/**
 * Circular progress ring used to surface reviewer scores.
 * The ring fills clockwise from the top, color-coded by score
 * band (good / warning / danger). Uses inline SVG so the same
 * component renders on mobile, tablet, and desktop.
 */
export function QualityRing({ score = 0, max = 10, size = 96, stroke = 8, label }) {
  const safeMax = Math.max(1, max);
  const safeScore = Math.max(0, Math.min(safeMax, score));
  const pct = safeScore / safeMax;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = circumference * pct;

  let color = '#EF4444'; // danger
  if (safeScore >= 8) color = '#22C55E';
  else if (safeScore >= 6) color = '#F59E0B';

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      aria-label={label || `Score ${safeScore} of ${safeMax}`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="rotate-[-90deg]"
        aria-hidden
      >
        <defs>
          <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#4F8CFF" />
            <stop offset="100%" stopColor="#7C5CFF" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          style={{ transition: 'stroke-dasharray 600ms ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn('text-2xl font-semibold tabular-nums text-white')}
        >
          {safeScore}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-text-muted">
          / {safeMax}
        </span>
      </div>
    </div>
  );
}
