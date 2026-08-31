import { Component, inject } from '@angular/core';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { duration, field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

/** The Voicemail section: caller, time, duration, trashed flag and transcript. */
@Component({
  selector: 'app-voicemail-section',
  imports: [ArtifactTable],
  template: `
    <app-artifact-table
      [columns]="columns"
      [fetchPage]="fetch"
      [searchable]="true"
      [detailFields]="detail"
      [detailTitle]="title"
    />
  `,
})
export class VoicemailSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'received_utc', label: 'Received', format: (r) => localTime(r['received_utc']) },
    { key: 'sender', label: 'From' },
    {
      key: 'duration_seconds',
      label: 'Duration',
      numeric: true,
      format: (r) => duration(r['duration_seconds']),
    },
    { key: 'trashed', label: 'Trashed', format: (r) => (r['trashed'] ? 'yes' : '') },
    { key: 'transcript', label: 'Transcript' },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.voicemail(q)) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('From', r['sender']),
    ...field('Received', localTime(r['received_utc'])),
    ...field('Duration', duration(r['duration_seconds'])),
    ...field('Trashed', r['trashed'] ? 'yes' : ''),
    ...field('Transcript', r['transcript'], true),
  ];

  protected readonly title = (r: TableRow): string => String(r['sender'] || 'Voicemail');
}
