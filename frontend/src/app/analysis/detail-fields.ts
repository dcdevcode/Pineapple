import type { DeviceFacts } from './analysis.models';
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

/** `m:ss` for a number of seconds (floored, so 119.6s is 1:59 not 1:60). */
export function duration(seconds: unknown): string {
  const total = Math.floor(Number(seconds));
  if (!Number.isFinite(total) || total <= 0) return '0:00';
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/** A one-line "model · iOS x · serial" summary of a device, from whichever
 *  fields are present. */
export function deviceLine(facts: DeviceFacts | null | undefined): string {
  const d = facts ?? {};
  return [
    d.product_name ?? d.product_type,
    d.product_version ? `iOS ${d.product_version}` : null,
    d.serial,
  ]
    .filter(Boolean)
    .join(' · ');
}
