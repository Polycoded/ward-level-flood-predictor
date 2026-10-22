// Rainfall inputs required by the problem statement: manual value, uploaded CSV,
// or a live forecast from a public weather API (Open-Meteo, no key needed).

/** Limits accepted by the API (api/schemas.py RainfallInput). */
export const MAX_RAINFALL_MM = 500;
export const MIN_DURATION_H = 1;
export const MAX_DURATION_H = 24;

export const MAX_CSV_BYTES = 64 * 1024;
const MAX_CSV_ROWS = 24;

export type RainfallSource = 'manual' | 'csv' | 'open-meteo';

export interface RainfallReading {
  rainfall_mm: number;
  duration_hours: number;
  source: RainfallSource;
  label: string;
  /** hourly values, when the source provides them */
  series?: number[];
}

export class RainfallInputError extends Error {}

export function clampRainfall(mm: number): number {
  if (!Number.isFinite(mm)) return 0;
  return Math.round(Math.min(MAX_RAINFALL_MM, Math.max(0, mm)) * 10) / 10;
}

export function clampDuration(hours: number): number {
  if (!Number.isFinite(hours)) return 3;
  return Math.min(MAX_DURATION_H, Math.max(MIN_DURATION_H, Math.round(hours)));
}

/**
 * Parse an hourly rainfall CSV. Accepted shapes, one row per hour:
 *   rainfall_mm            (single column, optional header)
 *   time,rainfall_mm       (value is the last column)
 * Rejects anything that is not a non-negative number so a bad file never
 * silently becomes "0 mm".
 */
export function parseRainfallCsv(text: string, fileName = 'upload.csv'): RainfallReading {
  if (text.length > MAX_CSV_BYTES) throw new RainfallInputError('CSV is too large (max 64 KB).');

  const lines = text
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length === 0) throw new RainfallInputError('CSV is empty.');

  const lastCell = (line: string) => line.split(/[,;\t]/).pop()!.trim().replace(/^"|"$/g, '');
  const rows = /[a-z]/i.test(lastCell(lines[0])) ? lines.slice(1) : lines;
  if (rows.length === 0) throw new RainfallInputError('CSV has a header but no values.');
  if (rows.length > MAX_CSV_ROWS) {
    throw new RainfallInputError(`CSV has ${rows.length} rows; at most ${MAX_CSV_ROWS} hourly values are supported.`);
  }

  const series = rows.map((line, i) => {
    const cell = lastCell(line);
    const value = Number(cell);
    if (cell === '' || !Number.isFinite(value)) {
      throw new RainfallInputError(`Row ${i + 1}: "${cell.slice(0, 20)}" is not a number.`);
    }
    if (value < 0) throw new RainfallInputError(`Row ${i + 1}: rainfall cannot be negative.`);
    if (value > MAX_RAINFALL_MM) throw new RainfallInputError(`Row ${i + 1}: ${value} mm in one hour is not plausible.`);
    return value;
  });

  const total = series.reduce((a, b) => a + b, 0);
  if (total > MAX_RAINFALL_MM) {
    throw new RainfallInputError(`Total of ${total.toFixed(0)} mm exceeds the ${MAX_RAINFALL_MM} mm the model accepts.`);
  }

  return {
    rainfall_mm: clampRainfall(total),
    duration_hours: clampDuration(series.length),
    source: 'csv',
    label: fileName.slice(0, 40),
    series,
  };
}

// Greater Chennai Corporation centroid; a city-wide forecast is what IMD issues too.
export const CHENNAI = { latitude: 13.0827, longitude: 80.2707 };

interface OpenMeteoResponse {
  hourly?: { time?: string[]; precipitation?: (number | null)[] };
}

/** Sum the next `hours` of Open-Meteo hourly precipitation, starting from the current hour. */
export function summariseOpenMeteo(data: OpenMeteoResponse, hours: number, now = new Date()): RainfallReading {
  const times = data.hourly?.time;
  const precip = data.hourly?.precipitation;
  if (!Array.isArray(times) || !Array.isArray(precip) || times.length !== precip.length) {
    throw new RainfallInputError('Unexpected response from the weather service.');
  }
  // Open-Meteo returns ISO times without a zone when timezone=GMT; treat as UTC.
  const startIdx = times.findIndex((t) => new Date(`${t}Z`).getTime() + 3600_000 > now.getTime());
  if (startIdx < 0) throw new RainfallInputError('Forecast does not cover the coming hours.');

  const series = precip.slice(startIdx, startIdx + hours).map((v) => (typeof v === 'number' && v > 0 ? v : 0));
  if (series.length === 0) throw new RainfallInputError('Forecast does not cover the coming hours.');

  return {
    rainfall_mm: clampRainfall(series.reduce((a, b) => a + b, 0)),
    duration_hours: clampDuration(series.length),
    source: 'open-meteo',
    label: `Open-Meteo next ${series.length}h`,
    series,
  };
}

export async function fetchOpenMeteoForecast(hours: number, signal?: AbortSignal): Promise<RainfallReading> {
  const url = new URL('https://api.open-meteo.com/v1/forecast');
  url.searchParams.set('latitude', String(CHENNAI.latitude));
  url.searchParams.set('longitude', String(CHENNAI.longitude));
  url.searchParams.set('hourly', 'precipitation');
  url.searchParams.set('forecast_days', '2');
  url.searchParams.set('timezone', 'GMT');

  const res = await fetch(url, { signal });
  if (!res.ok) throw new RainfallInputError(`Weather service returned ${res.status}.`);
  return summariseOpenMeteo(await res.json(), clampDuration(hours));
}
