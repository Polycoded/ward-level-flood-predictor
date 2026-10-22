import { describe, expect, it } from 'vitest';
import { MAX_CSV_BYTES, RainfallInputError, clampDuration, clampRainfall, parseRainfallCsv, summariseOpenMeteo } from './rainfall';

describe('parseRainfallCsv', () => {
  it('reads a single-column hourly series with header', () => {
    const r = parseRainfallCsv('rainfall_mm\n10\n25.5\n40\n', 'storm.csv');
    expect(r).toMatchObject({ rainfall_mm: 75.5, duration_hours: 3, source: 'csv', label: 'storm.csv' });
    expect(r.series).toEqual([10, 25.5, 40]);
  });

  it('reads time,value rows, CRLF endings, BOM and quoted cells', () => {
    const csv = '﻿time,rainfall_mm\r\n2023-12-04T00:00,"60"\r\n2023-12-04T01:00,80\r\n';
    expect(parseRainfallCsv(csv).rainfall_mm).toBe(140);
  });

  it('accepts semicolon and tab separated files', () => {
    expect(parseRainfallCsv('t;mm\n1;5\n2;5').rainfall_mm).toBe(10);
    expect(parseRainfallCsv('t\tmm\n1\t7').rainfall_mm).toBe(7);
  });

  it.each([
    ['empty file', ''],
    ['header only', 'rainfall_mm\n'],
    ['non-numeric value', 'mm\n10\nabc\n'],
    ['blank cell', 'time,mm\n01:00,\n'],
    ['negative value', 'mm\n-5\n'],
    ['implausible hourly value', 'mm\n9999\n'],
    ['total above API limit', 'mm\n' + Array(24).fill(30).join('\n')],
    ['too many rows', 'mm\n' + Array(25).fill(1).join('\n')],
    ['Infinity', 'mm\nInfinity\n'],
    ['spreadsheet formula', 'mm\n=HYPERLINK("http://evil")\n'],
  ])('rejects %s with a readable error', (_, csv) => {
    expect(() => parseRainfallCsv(csv)).toThrow(RainfallInputError);
  });

  it('rejects files over the size limit before parsing', () => {
    expect(() => parseRainfallCsv('1\n'.repeat(MAX_CSV_BYTES))).toThrow(/too large/);
  });

  it('caps the label length so a long filename cannot break the layout', () => {
    expect(parseRainfallCsv('5', 'x'.repeat(500)).label).toHaveLength(40);
  });
});

describe('clamp helpers', () => {
  it('keeps values inside the API limits', () => {
    expect(clampRainfall(-10)).toBe(0);
    expect(clampRainfall(9000)).toBe(500);
    expect(clampRainfall(Number.NaN)).toBe(0);
    expect(clampDuration(0)).toBe(1);
    expect(clampDuration(48)).toBe(24);
    expect(clampDuration(Number.NaN)).toBe(3);
  });
});

describe('summariseOpenMeteo', () => {
  // Shape of a real https://api.open-meteo.com/v1/forecast?hourly=precipitation&timezone=GMT response
  const response = {
    latitude: 13.08,
    longitude: 80.27,
    hourly_units: { time: 'iso8601', precipitation: 'mm' },
    hourly: {
      time: ['2026-10-22T10:00', '2026-10-22T11:00', '2026-10-22T12:00', '2026-10-22T13:00', '2026-10-22T14:00'],
      precipitation: [1.0, 2.5, null, 4.0, 10.0],
    },
  };

  it('sums the coming hours starting at the current hour', () => {
    const now = new Date('2026-10-22T11:20:00Z');
    const r = summariseOpenMeteo(response, 3, now);
    expect(r.series).toEqual([2.5, 0, 4]);
    expect(r.rainfall_mm).toBe(6.5);
    expect(r.duration_hours).toBe(3);
    expect(r.source).toBe('open-meteo');
  });

  it('rejects malformed responses', () => {
    expect(() => summariseOpenMeteo({}, 6)).toThrow(RainfallInputError);
    expect(() => summariseOpenMeteo({ hourly: { time: ['2026-10-22T10:00'], precipitation: [] } }, 6)).toThrow(RainfallInputError);
  });

  it('rejects a stale forecast', () => {
    expect(() => summariseOpenMeteo(response, 3, new Date('2027-01-01T00:00:00Z'))).toThrow(/coming hours/);
  });
});
