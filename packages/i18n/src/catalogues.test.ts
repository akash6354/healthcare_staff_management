import { describe, expect, it } from 'vitest';
import { en } from './en';
import { hi } from './hi';
import { kn } from './kn';
import { errorKey, format } from './index';

const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();

describe('catalogues', () => {
  it.each([
    ['kn', kn],
    ['hi', hi],
  ])('%s has every English key with the same placeholders', (_, cat) => {
    expect(Object.keys(cat).sort()).toEqual(Object.keys(en).sort());
    for (const [key, value] of Object.entries(en)) {
      expect(placeholders((cat as Record<string, string>)[key]!), key).toEqual(placeholders(value));
      expect((cat as Record<string, string>)[key]!.trim().length, key).toBeGreaterThan(0);
    }
  });

  it('never claims NABH compliance or certification', () => {
    for (const cat of [en, kn, hi]) {
      for (const value of Object.values(cat)) {
        expect(value).not.toMatch(/NABH (compliant|certified)/i);
      }
    }
  });

  it('formats params and maps API error codes', () => {
    expect(format('Due in {minutes} min', { minutes: 5 })).toBe('Due in 5 min');
    expect(errorKey('INVALID_CODE')).toBe('errors.invalid_code');
    expect(errorKey('SOMETHING_NEW')).toBe('errors.generic');
  });
});
