import { deviceLine, duration, field, localTime } from './detail-fields';

describe('field', () => {
  it('drops empty values', () => {
    expect(field('X', null)).toEqual([]);
    expect(field('X', undefined)).toEqual([]);
    expect(field('X', '')).toEqual([]);
  });

  it('stringifies a present value', () => {
    expect(field('Count', 3)).toEqual([{ label: 'Count', value: '3', long: false }]);
    expect(field('Body', 'hi', true)).toEqual([{ label: 'Body', value: 'hi', long: true }]);
  });
});

describe('localTime', () => {
  it('formats an ISO string to a local string', () => {
    const out = localTime('2026-01-02T03:04:05Z');
    expect(out).not.toBe('2026-01-02T03:04:05Z');
    expect(out.length).toBeGreaterThan(0);
  });

  it('passes non-dates and empty values straight through', () => {
    expect(localTime('not a date')).toBe('not a date');
    expect(localTime('')).toBe('');
    expect(localTime(42)).toBe('');
  });
});

describe('duration', () => {
  it('formats seconds as m:ss', () => {
    expect(duration(0)).toBe('0:00');
    expect(duration(9)).toBe('0:09');
    expect(duration(65)).toBe('1:05');
    expect(duration(600)).toBe('10:00');
  });

  it('floors fractional seconds so 119.6 is 1:59, not 1:60', () => {
    expect(duration(119.6)).toBe('1:59');
  });

  it('guards non-numbers and non-positive values', () => {
    expect(duration('nope')).toBe('0:00');
    expect(duration(-4)).toBe('0:00');
    expect(duration(null)).toBe('0:00');
  });
});

describe('deviceLine', () => {
  it('joins the present fields with a middot', () => {
    expect(deviceLine({ product_name: 'iPhone 13', product_version: '17.5', serial: 'F17' })).toBe(
      'iPhone 13 · iOS 17.5 · F17',
    );
  });

  it('falls back to product_type and skips missing fields', () => {
    expect(deviceLine({ product_type: 'iPhone14,5', serial: 'F17' })).toBe('iPhone14,5 · F17');
  });

  it('is empty for null / empty facts', () => {
    expect(deviceLine(null)).toBe('');
    expect(deviceLine({})).toBe('');
  });
});
