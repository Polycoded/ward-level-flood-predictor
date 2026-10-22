// Helpers for rendering data that came from the API or from users.
// Ward names come from OpenStreetMap, alert links from the backend — neither is trusted.

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Escape text before it goes into an HTML string (Leaflet tooltips take raw HTML). */
export function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

const WHATSAPP_HOSTS = new Set(['wa.me', 'api.whatsapp.com']);

/**
 * Returns the URL only if it is an https WhatsApp share link with no recipient baked in,
 * otherwise null. Blocks javascript:/data: URLs, look-alike hosts such as wa.me.evil.com,
 * and links that pre-address a phone number (an alert must go where the official chooses,
 * not to a number that came back from the server).
 */
export function safeWhatsAppUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' || !WHATSAPP_HOSTS.has(parsed.hostname)) return null;
    if (parsed.username || parsed.password || parsed.port) return null;
    if (parsed.hostname === 'wa.me' && parsed.pathname !== '/') return null;
    if (parsed.hostname === 'api.whatsapp.com' && (parsed.pathname !== '/send' || parsed.searchParams.has('phone'))) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

/** Share link that lets the official pick the recipient group in WhatsApp. */
export function whatsAppShareUrl(message: string): string {
  return `https://wa.me/?text=${encodeURIComponent(message)}`;
}

/** Strip control characters and clamp length for free-text user input. */
export function sanitizeText(input: string, maxLength: number): string {
  // eslint-disable-next-line no-control-regex
  return input.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '').trim().slice(0, maxLength);
}
