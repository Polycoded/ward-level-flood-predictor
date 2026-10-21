import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number, decimals: number = 1): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(decimals) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(decimals) + 'K';
  }
  return num.toFixed(decimals);
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

export function formatTime(minutes: number): string {
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  }
  return `${minutes} min`;
}

export function getRiskColor(riskLevel: string): string {
  const colors: Record<string, string> = {
    very_low: '#10b981',
    low: '#84cc16',
    moderate: '#f59e0b',
    high: '#f97316',
    very_high: '#ef4444',
  };
  return colors[riskLevel] || '#6b7280';
}

export function getDepthColor(depthBand: string): string {
  const colors: Record<string, string> = {
    none: '#10b981',
    '0-0.15m': '#84cc16',
    '0.15-0.5m': '#f59e0b',
    '0.5-1.0m': '#f97316',
    '1.0m+': '#ef4444',
  };
  return colors[depthBand] || '#6b7280';
}

export function getRiskLabel(riskLevel: string): string {
  const labels: Record<string, string> = {
    very_low: 'Very Low',
    low: 'Low',
    moderate: 'Moderate',
    high: 'High',
    very_high: 'Very High',
  };
  return labels[riskLevel] || riskLevel;
}

export function getDepthLabel(depthBand: string): string {
  const labels: Record<string, string> = {
    none: 'No Flooding',
    '0-0.15m': '0-15 cm (Ankle)',
    '0.15-0.5m': '15-50 cm (Knee)',
    '0.5-1.0m': '50-100 cm (Waist)',
    '1.0m+': '1m+ (Over Head)',
  };
  return labels[depthBand] || depthBand;
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

export function throttle<T extends (...args: unknown[]) => unknown>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}