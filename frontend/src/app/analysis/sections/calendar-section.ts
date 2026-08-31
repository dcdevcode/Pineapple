import { Component, inject } from '@angular/core';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

/** The Calendar section: events with their calendar, location and invitees. */
@Component({
  selector: 'app-calendar-section',
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
export class CalendarSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'start_utc', label: 'Start', format: (r) => localTime(r['start_utc']) },
    { key: 'title', label: 'Title' },
    { key: 'calendar', label: 'Calendar' },
    { key: 'location', label: 'Location' },
    { key: 'all_day', label: 'All day', format: (r) => (r['all_day'] ? 'yes' : '') },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.calendar(q)) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('Title', r['title']),
    ...field('Calendar', r['calendar']),
    ...field('Location', r['location']),
    ...field('Start', localTime(r['start_utc'])),
    ...field('End', localTime(r['end_utc'])),
    ...field('All day', r['all_day'] ? 'yes' : ''),
    ...field('Invitees', r['invitees'], true),
    ...field('Notes', r['notes'], true),
  ];

  protected readonly title = (r: TableRow): string => String(r['title'] || 'Event');
}
