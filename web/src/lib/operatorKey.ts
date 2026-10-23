// The operator key authorises approving and cancelling alerts. It is entered by
// the official, kept only on this device, and sent as X-Admin-Token on those two
// actions — never baked into the bundle, so the secret is not shipped to everyone.
import { readJson, writeJson } from './persist';

const KEY = 'flood-operator-key';

export function getOperatorKey(): string {
  const value = readJson<unknown>(KEY, '');
  return typeof value === 'string' ? value : '';
}

export function setOperatorKey(value: string): void {
  const trimmed = value.trim();
  writeJson(KEY, trimmed || null);
}
