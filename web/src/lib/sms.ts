// How many SMS parts a message really costs. Tamil (and anything outside the GSM 03.38
// alphabet) is sent as UCS-2: 70 characters for one SMS, 67 per part when split.

const GSM_BASIC =
  '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';
const GSM_EXTENDED = '^{}\\[~]|€\f';

export interface SmsInfo {
  encoding: 'GSM-7' | 'UCS-2';
  /** length in the units the network counts (extended GSM chars count twice) */
  units: number;
  segments: number;
  /** capacity of a single SMS in this encoding */
  singleLimit: number;
}

export function smsInfo(text: string): SmsInfo {
  const chars = [...text];
  const gsm = chars.every((c) => GSM_BASIC.includes(c) || GSM_EXTENDED.includes(c));
  if (gsm) {
    const units = chars.reduce((n, c) => n + (GSM_EXTENDED.includes(c) ? 2 : 1), 0);
    return { encoding: 'GSM-7', units, segments: units <= 160 ? 1 : Math.ceil(units / 153), singleLimit: 160 };
  }
  // UCS-2 counts UTF-16 code units
  const units = text.length;
  return { encoding: 'UCS-2', units, segments: units <= 70 ? 1 : Math.ceil(units / 67), singleLimit: 70 };
}
