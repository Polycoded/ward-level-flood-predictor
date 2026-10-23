import { describe, expect, it } from 'vitest';
import { allMessageKeys, dictionaries, translate } from './i18n';

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('translations', () => {
  it('has a non-empty Tamil string for every English key, with the same placeholders', () => {
    for (const key of allMessageKeys) {
      expect(dictionaries.ta[key].trim().length, key).toBeGreaterThan(0);
      expect(placeholders(dictionaries.ta[key]), key).toEqual(placeholders(dictionaries.en[key]));
    }
  });

  it('really is Tamil where it should be', () => {
    const tamilScript = /[஀-௿]/;
    const untranslated = allMessageKeys.filter((k) => !tamilScript.test(dictionaries.ta[k]) && k !== 'lang.other');
    expect(untranslated).toEqual([]);
  });

  it('fills placeholders and leaves unknown ones visible', () => {
    expect(translate('en', 'shelter.walk', { min: 7 })).toBe('7 min walk');
    expect(translate('ta', 'sub.on', { ward: 'Ward 168' })).toContain('Ward 168');
    expect(translate('en', 'shelter.walk')).toBe('{min} min walk');
  });

  it('never promises depth, timing or certainty (model contract)', () => {
    for (const lang of ['en', 'ta'] as const) {
      for (const key of allMessageKeys) {
        expect(dictionaries[lang][key], key).not.toMatch(/knee|waist|ankle|deep|metre|peak|will flood|guarantee/i);
      }
    }
  });
});
