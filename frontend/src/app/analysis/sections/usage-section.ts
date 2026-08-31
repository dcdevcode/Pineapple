import { Component, inject } from '@angular/core';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { duration, field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

/** The Usage section: a curated slice of knowledgeC (app usage / focus /
 *  backlight / notifications). */
@Component({
  selector: 'app-usage-section',
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
export class UsageSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'start_utc', label: 'Start', format: (r) => localTime(r['start_utc']) },
    { key: 'stream', label: 'Stream' },
    { key: 'bundle_id', label: 'App' },
    { key: 'value', label: 'Value' },
    {
      key: 'duration_seconds',
      label: 'Duration',
      numeric: true,
      format: (r) => duration(r['duration_seconds']),
    },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.deviceUsage(q)) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('Stream', r['stream']),
    ...field('App', r['bundle_id']),
    ...field('Value', r['value']),
    ...field('Start', localTime(r['start_utc'])),
    ...field('End', localTime(r['end_utc'])),
    ...field('Duration', duration(r['duration_seconds'])),
  ];

  protected readonly title = (r: TableRow): string =>
    String(r['bundle_id'] || r['stream'] || 'Event');
}
