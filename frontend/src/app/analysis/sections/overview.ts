import { Component, computed, input } from '@angular/core';
import type { CaseSummary, DeviceFacts } from '../analysis.models';

interface Fact {
  label: string;
  value: string;
}

function text(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null;
  return String(value);
}

function bool(value: unknown): string {
  return value ? 'Yes' : 'No';
}

function localDate(value: unknown): string | null {
  const raw = text(value);
  if (raw === null) return raw;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleString();
}

const COUNT_LABELS: Record<string, string> = {
  files: 'Files',
  apps: 'Apps',
  messages: 'Messages',
  calls: 'Calls',
  contacts: 'Contacts',
  photos: 'Photos',
  calendar_events: 'Calendar events',
  voicemail: 'Voicemail',
  device_usage: 'Usage events',
  accounts: 'Accounts',
  keychain: 'Keychain items',
};

/** The case Overview: device facts, the parse report, and the source archive. */
@Component({
  selector: 'app-analysis-overview',
  templateUrl: './overview.html',
  styleUrl: './overview.scss',
})
export class Overview {
  readonly summary = input.required<CaseSummary>();

  protected readonly deviceFacts = computed<Fact[]>(() => {
    const d: DeviceFacts = this.summary().device;
    const rows: [string, string | null][] = [
      ['Name', text(d.device_name ?? d.name)],
      ['Model', text(d.product_name)],
      ['Product Type', text(d.product_type)],
      ['iOS Version', text(d.product_version)],
      ['Build', text(d.build_version)],
      ['Serial Number', text(d.serial)],
      ['UDID', text(d.udid)],
      ['Last Backup', localDate(d.last_backup_date)],
      ['Passcode Set', bool(d.was_passcode_set)],
      ['Encrypted Backup', bool(d.is_encrypted)],
    ];
    return rows
      .filter((row): row is [string, string] => row[1] !== null)
      .map(([label, value]) => ({ label, value }));
  });

  protected readonly counts = computed<Fact[]>(() => {
    const counts = this.summary().counts ?? {};
    return Object.entries(COUNT_LABELS)
      .filter(([key]) => key in counts)
      .map(([key, label]) => ({ label, value: String(counts[key]) }));
  });

  protected readonly skipped = computed(() => this.summary().parse?.skipped ?? []);

  protected readonly source = computed<Fact[]>(() => {
    const s = this.summary().source ?? {};
    const rows: [string, string | null][] = [
      ['File', text(s.path)],
      ['SHA-256', text(s.sha256)],
      ['Encrypted', bool(s.is_encrypted)],
    ];
    return rows
      .filter((row): row is [string, string] => row[1] !== null)
      .map(([label, value]) => ({ label, value }));
  });

  protected readonly parseStatus = computed(() => this.summary().parse?.status ?? 'unknown');
}
