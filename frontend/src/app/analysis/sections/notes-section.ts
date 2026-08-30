import { Component, inject } from '@angular/core';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

/** The Notes section: title / folder / snippet in the table, full body in the detail dialog. */
@Component({
  selector: 'app-notes-section',
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
export class NotesSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'modified_utc', label: 'Modified', format: (r) => localTime(r['modified_utc']) },
    { key: 'folder', label: 'Folder' },
    { key: 'title', label: 'Title' },
    { key: 'snippet', label: 'Snippet' },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.notes(q)) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('Title', r['title']),
    ...field('Folder', r['folder']),
    ...field('Created', localTime(r['created_utc'])),
    ...field('Modified', localTime(r['modified_utc'])),
    ...field('Body', r['body'] || r['snippet'], true),
  ];

  protected readonly title = (r: TableRow): string => String(r['title'] || 'Note');
}
