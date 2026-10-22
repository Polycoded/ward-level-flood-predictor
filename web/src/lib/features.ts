/** Tier 3 crowd reports are off unless explicitly enabled at build time. */
export const CROWD_REPORTS_ENABLED = import.meta.env.VITE_ENABLE_CROWD_REPORTS === 'true';
