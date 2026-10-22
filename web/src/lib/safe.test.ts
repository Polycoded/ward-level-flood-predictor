import { describe, expect, it } from 'vitest';
import { escapeHtml, safeWhatsAppUrl, sanitizeText, whatsAppShareUrl } from './safe';

describe('escapeHtml', () => {
  it('neutralises markup and attribute breakouts', () => {
    expect(escapeHtml('<img src=x onerror=alert(1)>')).toBe('&lt;img src=x onerror=alert(1)&gt;');
    expect(escapeHtml(`" onmouseover='x'`)).toBe('&quot; onmouseover=&#39;x&#39;');
    expect(escapeHtml('Ward 12 & Co')).toBe('Ward 12 &amp; Co');
  });

  it('handles non-strings', () => {
    expect(escapeHtml(null)).toBe('');
    expect(escapeHtml(42)).toBe('42');
  });
});

describe('safeWhatsAppUrl', () => {
  it('accepts number-less share links', () => {
    expect(safeWhatsAppUrl('https://wa.me/?text=hello')).toBe('https://wa.me/?text=hello');
    expect(safeWhatsAppUrl('https://api.whatsapp.com/send?text=hi')).toBe('https://api.whatsapp.com/send?text=hi');
  });

  it.each([
    ['javascript URL', 'javascript:alert(document.cookie)'],
    ['data URL', 'data:text/html,<script>alert(1)</script>'],
    ['plain http', 'http://wa.me/?text=x'],
    ['look-alike host', 'https://wa.me.evil.example/?text=x'],
    ['subdomain trick', 'https://evil.example/wa.me/?text=x'],
    ['credentials in URL', 'https://user:pass@wa.me/?text=x'],
    ['custom port', 'https://wa.me:8443/?text=x'],
    ['pre-addressed number (wa.me)', 'https://wa.me/919876543210?text=x'],
    ['pre-addressed number (api)', 'https://api.whatsapp.com/send?phone=919876543210&text=x'],
    ['garbage', 'not a url'],
    ['empty', ''],
  ])('rejects %s', (_, url) => {
    expect(safeWhatsAppUrl(url)).toBeNull();
  });

  it('builds share links that round-trip Tamil text', () => {
    const msg = 'அதிக வெள்ள அபாயம்! & more';
    const url = whatsAppShareUrl(msg);
    expect(safeWhatsAppUrl(url)).not.toBeNull();
    expect(new URL(url).searchParams.get('text')).toBe(msg);
  });
});

describe('sanitizeText', () => {
  it('strips control characters, trims and clamps', () => {
    expect(sanitizeText('  water\u0000 at\u0007 knee  ', 100)).toBe('water at knee');
    expect(sanitizeText('a'.repeat(500), 280)).toHaveLength(280);
    expect(sanitizeText('line1\nline2', 50)).toBe('line1\nline2');
  });
});
