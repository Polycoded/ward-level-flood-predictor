import { cn } from '../lib/utils';
import { getRiskColor, getRiskLabel } from '../lib/utils';
import type { RiskLevel } from '../types';

interface RiskBadgeProps {
  level: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export function RiskBadge({ level, size = 'md', showIcon = false }: RiskBadgeProps) {
  const color = getRiskColor(level);
  const label = getRiskLabel(level);

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-medium',
        sizeClasses[size],
        'border'
      )}
      style={{ backgroundColor: `${color}1a`, color, borderColor: `${color}33` }}
    >
      {showIcon && <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />}
      {label}
    </span>
  );
}