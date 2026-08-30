import { Component, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatListModule } from '@angular/material/list';
import { AnalysisService } from './analysis.service';
import { AnalysisDialog } from './analysis-dialog';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from './artifact-table';
import { FilesSection } from './sections/files-section';
import { Overview } from './sections/overview';
import type { DeviceFacts, Page, PageQuery } from './analysis.models';

type SectionId = 'overview' | 'apps' | 'files' | 'messages' | 'calls' | 'contacts';

interface Section {
  id: SectionId;
  label: string;
}

function localTime(value: unknown): string {
  if (typeof value !== 'string' || !value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function duration(seconds: unknown): string {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total <= 0) return '0:00';
  const mins = Math.floor(total / 60);
  const secs = Math.round(total % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/** The Analysis tab: a launcher until a case is open, then the case browser. */
@Component({
  selector: 'app-analysis',
  imports: [MatButtonModule, MatListModule, ArtifactTable, FilesSection, Overview],
  templateUrl: './analysis.html',
  styleUrl: './analysis.scss',
})
export class Analysis {
  private readonly analysis = inject(AnalysisService);
  private readonly dialog = inject(MatDialog);

  readonly summary = this.analysis.summary;
  protected readonly active = signal<SectionId>('overview');
  protected readonly launcherError = signal<string | null>(null);
  protected readonly busy = signal(false);

  protected readonly sections: readonly Section[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'apps', label: 'Apps' },
    { id: 'files', label: 'Files' },
    { id: 'messages', label: 'Messages' },
    { id: 'calls', label: 'Calls' },
    { id: 'contacts', label: 'Contacts' },
  ];

  protected readonly deviceLine = computed(() => {
    const d: DeviceFacts = this.summary()?.device ?? {};
    return [
      d.product_name ?? d.product_type,
      d.product_version ? `iOS ${d.product_version}` : null,
      d.serial,
    ]
      .filter(Boolean)
      .join(' · ');
  });

  protected count(id: SectionId): number | null {
    const counts = this.summary()?.counts ?? {};
    return id in counts ? counts[id] : null;
  }

  // -- section table configs ------------------------------------------

  protected readonly appColumns: readonly ColumnDef[] = [
    { key: 'name', label: 'Name' },
    { key: 'bundle_id', label: 'Bundle ID' },
    { key: 'version', label: 'Version' },
  ];
  protected readonly fetchApps: FetchPage = async (q: PageQuery) => {
    const all = await this.analysis.apps();
    return this.slice(all as unknown as TableRow[], q);
  };

  protected readonly messageColumns: readonly ColumnDef[] = [
    { key: 'date_utc', label: 'Date', format: (r) => localTime(r['date_utc']) },
    { key: 'address', label: 'Contact' },
    {
      key: 'is_from_me',
      label: 'Direction',
      format: (r) => (r['is_from_me'] ? 'Sent' : 'Received'),
    },
    { key: 'text', label: 'Message' },
    { key: 'attachments', label: 'Att.', numeric: true },
  ];
  protected readonly fetchMessages: FetchPage = async (q: PageQuery) =>
    (await this.analysis.messages(q)) as unknown as Page<TableRow>;

  protected readonly callColumns: readonly ColumnDef[] = [
    { key: 'date_utc', label: 'Date', format: (r) => localTime(r['date_utc']) },
    { key: 'address', label: 'Number' },
    { key: 'direction', label: 'Direction' },
    { key: 'service', label: 'Service' },
    {
      key: 'duration_seconds',
      label: 'Duration',
      numeric: true,
      format: (r) => duration(r['duration_seconds']),
    },
  ];
  protected readonly fetchCalls: FetchPage = async (q: PageQuery) =>
    (await this.analysis.calls(q)) as unknown as Page<TableRow>;

  protected readonly contactColumns: readonly ColumnDef[] = [
    {
      key: 'last',
      label: 'Name',
      format: (r) => [r['first'], r['last']].filter(Boolean).join(' ') || '—',
    },
    { key: 'organization', label: 'Organization' },
    { key: 'phones', label: 'Phones' },
    { key: 'emails', label: 'Emails' },
  ];
  protected readonly fetchContacts: FetchPage = async (q: PageQuery) =>
    (await this.analysis.contacts(q)) as unknown as Page<TableRow>;

  // -- launcher actions ---------------------------------------------

  newAnalysis(): void {
    this.dialog.open(AnalysisDialog, {
      width: 'min(560px, 92vw)',
      maxWidth: '92vw',
      autoFocus: false,
    });
  }

  async openExisting(): Promise<void> {
    this.launcherError.set(null);
    this.busy.set(true);
    try {
      const picked = await this.analysis.chooseCaseFolder();
      if (!picked.ok) return;
      const opened = await this.analysis.openCase(picked.path);
      if (!opened.ok) this.launcherError.set(opened.error ?? 'Could not open that folder.');
      else this.active.set('overview');
    } finally {
      this.busy.set(false);
    }
  }

  close(): void {
    this.analysis.closeCase();
    this.active.set('overview');
  }

  private slice(rows: TableRow[], q: PageQuery): Page<TableRow> {
    return {
      rows: rows.slice(q.offset, q.offset + q.limit),
      total: rows.length,
      limit: q.limit,
      offset: q.offset,
    };
  }
}
