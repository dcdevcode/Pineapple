import { Component, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatListModule } from '@angular/material/list';
import { AnalysisService } from './analysis.service';
import { AnalysisDialog } from './analysis-dialog';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from './artifact-table';
import { AccountsSection } from './sections/accounts-section';
import { CalendarSection } from './sections/calendar-section';
import { FilesSection } from './sections/files-section';
import { NotesSection } from './sections/notes-section';
import { Overview } from './sections/overview';
import { PhotosSection } from './sections/photos-section';
import { SafariSection } from './sections/safari-section';
import { UsageSection } from './sections/usage-section';
import { VoicemailSection } from './sections/voicemail-section';
import { WhatsappSection } from './sections/whatsapp-section';
import { deviceLine, duration, field, localTime, type DetailBuilder } from './detail-fields';
import type { Page, PageQuery } from './analysis.models';

type SectionId =
  | 'overview'
  | 'apps'
  | 'files'
  | 'messages'
  | 'calls'
  | 'contacts'
  | 'notes'
  | 'photos'
  | 'calendar'
  | 'voicemail'
  | 'usage'
  | 'accounts'
  | 'safari'
  | 'whatsapp';

interface Section {
  id: SectionId;
  label: string;
}

/** The Analysis tab: a launcher until a case is open, then the case browser. */
@Component({
  selector: 'app-analysis',
  imports: [
    MatButtonModule,
    MatListModule,
    ArtifactTable,
    AccountsSection,
    CalendarSection,
    FilesSection,
    NotesSection,
    Overview,
    PhotosSection,
    SafariSection,
    UsageSection,
    VoicemailSection,
    WhatsappSection,
  ],
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
    { id: 'notes', label: 'Notes' },
    { id: 'photos', label: 'Photos' },
    { id: 'calendar', label: 'Calendar' },
    { id: 'voicemail', label: 'Voicemail' },
    { id: 'usage', label: 'Usage' },
    { id: 'accounts', label: 'Accounts' },
    { id: 'safari', label: 'Safari' },
    { id: 'whatsapp', label: 'WhatsApp' },
  ];

  protected readonly deviceLine = computed(() => deviceLine(this.summary()?.device));

  private readonly countKeys: Partial<Record<SectionId, readonly string[]>> = {
    apps: ['apps'],
    files: ['files'],
    messages: ['messages'],
    calls: ['calls'],
    contacts: ['contacts'],
    notes: ['notes'],
    photos: ['photos'],
    calendar: ['calendar_events'],
    voicemail: ['voicemail'],
    usage: ['device_usage'],
    accounts: ['accounts'],
    safari: ['safari_history', 'safari_bookmarks'],
    whatsapp: ['whatsapp_messages'],
  };

  protected count(id: SectionId): number | null {
    const counts = this.summary()?.counts ?? {};
    const keys = this.countKeys[id];
    if (!keys) return null;
    const present = keys.filter((k) => k in counts);
    return present.length ? present.reduce((sum, k) => sum + counts[k], 0) : null;
  }

  // -- detail-dialog titles -----------------------------------------

  protected readonly appTitle = (r: TableRow): string =>
    String(r['name'] || r['bundle_id'] || 'App');
  protected readonly addressTitle = (r: TableRow): string => String(r['address'] || 'Record');
  protected readonly contactTitle = (r: TableRow): string =>
    [r['first'], r['last']].filter(Boolean).join(' ') || 'Contact';

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
  protected readonly appDetail: DetailBuilder = (r) => [
    ...field('Name', r['name']),
    ...field('Bundle ID', r['bundle_id']),
    ...field('Version', r['version']),
  ];

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
  protected readonly messageDetail: DetailBuilder = (r) => [
    ...field('Date', localTime(r['date_utc'])),
    ...field('Contact', r['address']),
    ...field('Direction', r['is_from_me'] ? 'Sent' : 'Received'),
    ...field('Service', r['service']),
    ...field('Chat ID', r['chat_id']),
    ...field('Attachments', r['attachments']),
    ...field('Message', r['text'], true),
  ];

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
  protected readonly callDetail: DetailBuilder = (r) => [
    ...field('Date', localTime(r['date_utc'])),
    ...field('Number', r['address']),
    ...field('Direction', r['direction']),
    ...field('Service', r['service']),
    ...field('Duration', duration(r['duration_seconds'])),
  ];

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
  protected readonly contactDetail: DetailBuilder = (r) => [
    ...field('Name', [r['first'], r['last']].filter(Boolean).join(' ')),
    ...field('Organization', r['organization']),
    ...field('Phones', r['phones'], true),
    ...field('Emails', r['emails'], true),
  ];

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
