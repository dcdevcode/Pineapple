import type { TableRow } from './artifact-table';
import type { DetailField } from './record-detail-dialog';

/** Builds the detail-dialog fields for one artifact-table row. */
export type DetailBuilder = (row: TableRow) => DetailField[];

/** A detail field, skipped entirely when the value is empty. */
export function field(label: string, value: unknown, long = false): DetailField[] {
  if (value === null || value === undefined || value === '') return [];
  return [{ label, value: String(value), long }];
}

/** Local-time string for an ISO-8601 UTC value; passthrough on anything else. */
export function localTime(value: unknown): string {
  if (typeof value !== 'string' || !value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

/** `m:ss` for a whole number of seconds. */
export function duration(seconds: unknown): string {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total <= 0) return '0:00';
  const mins = Math.floor(total / 60);
  const secs = Math.round(total % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
