import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

type View = 'history' | 'bookmarks';

/** The Safari section: a History / Bookmarks toggle over two artifact tables. */
@Component({
  selector: 'app-safari-section',
  imports: [ArtifactTable, FormsModule, MatButtonToggleModule],
  templateUrl: './safari-section.html',
  styleUrl: './safari-section.scss',
})
export class SafariSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly view = signal<View>('history');

  protected readonly historyColumns: readonly ColumnDef[] = [
    { key: 'visit_utc', label: 'Visited', format: (r) => localTime(r['visit_utc']) },
    { key: 'title', label: 'Title' },
    { key: 'url', label: 'URL' },
    { key: 'visit_count', label: 'Visits', numeric: true },
  ];
  protected readonly bookmarkColumns: readonly ColumnDef[] = [
    { key: 'folder', label: 'Folder' },
    { key: 'title', label: 'Title' },
    { key: 'url', label: 'URL' },
  ];

  protected readonly fetchHistory: FetchPage = async (q: PageQuery) =>
    (await this.analysis.safariHistory(q)) as unknown as Page<TableRow>;
  protected readonly fetchBookmarks: FetchPage = async (q: PageQuery) =>
    (await this.analysis.safariBookmarks(q)) as unknown as Page<TableRow>;

  protected readonly historyDetail: DetailBuilder = (r) => [
    ...field('Title', r['title']),
    ...field('URL', r['url'], true),
    ...field('Visited', localTime(r['visit_utc'])),
    ...field('Visit count', r['visit_count']),
  ];
  protected readonly bookmarkDetail: DetailBuilder = (r) => [
    ...field('Title', r['title']),
    ...field('URL', r['url'], true),
    ...field('Folder', r['folder']),
  ];

  protected readonly urlTitle = (r: TableRow): string => String(r['title'] || r['url'] || 'Entry');
}
