import {
  Component,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  signal,
  DestroyRef,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import type { FilePreview, Page, PageQuery } from './analysis.models';
import { RecordDetailDialog, type DetailField } from './record-detail-dialog';

export type Cell = string | number | boolean | null;
export type TableRow = Record<string, Cell>;

/** One column of an {@link ArtifactTable}. */
export interface ColumnDef {
  key: string;
  label: string;
  /** Derived display text; defaults to the raw `row[key]`. */
  format?: (row: TableRow) => string;
  /** Right-align (numbers). */
  numeric?: boolean;
}

export type FetchPage = (query: PageQuery) => Promise<Page<TableRow>>;

const SEARCH_DEBOUNCE_MS = 250;
const PAGE_SIZE_OPTIONS = [25, 50, 100, 250];

/**
 * A paged, optionally searchable table over one `analysis_*` query. Owns the
 * fetch loop: it re-runs {@link fetchPage} whenever the page or the (debounced)
 * search term changes and renders loading / empty / error states.
 *
 * A searchable table shows a toolbar row: project a filter control into it with
 * the `tableFilter` attribute (`<mat-form-field tableFilter>` / a toggle group)
 * and it sits to the left of the Search field.
 */
@Component({
  selector: 'app-artifact-table',
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatPaginatorModule,
    MatProgressBarModule,
    MatTableModule,
  ],
  templateUrl: './artifact-table.html',
  styleUrl: './artifact-table.scss',
})
export class ArtifactTable {
  readonly columns = input.required<readonly ColumnDef[]>();
  readonly fetchPage = input.required<FetchPage>();
  readonly searchable = input(false);
  readonly pageSize = input(50);
  /** Bumping this (e.g. a domain filter changed) resets to page 0 and refetches. */
  readonly scope = input<unknown>(null);
  /** When set, a row click opens the detail dialog with these fields. */
  readonly detailFields = input<((row: TableRow) => DetailField[]) | null>(null);
  readonly detailTitle = input<((row: TableRow) => string) | null>(null);
  /** Files only: resolve the content preview shown inside the detail dialog. */
  readonly resolvePreview = input<((row: TableRow) => Promise<FilePreview | null>) | null>(null);
  /** Files only: the Extract action inside the detail dialog. */
  readonly onExtract = input<
    ((row: TableRow) => Promise<{ ok: boolean; path?: string; error?: string }>) | null
  >(null);

  private readonly dialog = inject(MatDialog);

  protected readonly pageSizeOptions = PAGE_SIZE_OPTIONS;

  protected readonly rows = signal<TableRow[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly search = signal('');
  private readonly debouncedSearch = signal('');
  /** Page size; seeded from the input, then owned by the paginator. */
  protected readonly size = linkedSignal(() => this.pageSize());
  /** Current page. Snaps back to 0 whenever the scope or search term changes. */
  protected readonly index = linkedSignal(() => {
    this.scope();
    this.debouncedSearch();
    return 0;
  });

  protected readonly displayColumns = computed(() => this.columns().map((c) => c.key));

  private searchTimer: ReturnType<typeof setTimeout> | null = null;
  private requestId = 0;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      if (this.searchTimer !== null) clearTimeout(this.searchTimer);
    });

    effect(() => {
      const query: PageQuery = {
        limit: this.size(),
        offset: this.index() * this.size(),
        search: this.debouncedSearch() || undefined,
      };
      this.scope(); // track: a new scope must refetch even at offset 0
      void this.load(query);
    });
  }

  protected onSearch(value: string): void {
    this.search.set(value);
    if (this.searchTimer !== null) clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.debouncedSearch.set(value.trim()), SEARCH_DEBOUNCE_MS);
  }

  protected onPage(event: PageEvent): void {
    this.size.set(event.pageSize);
    this.index.set(event.pageIndex);
  }

  protected cell(row: TableRow, column: ColumnDef): string {
    if (column.format) return column.format(row);
    const value = row[column.key];
    return value === null || value === undefined ? '' : String(value);
  }

  protected get interactive(): boolean {
    return this.detailFields() !== null;
  }

  protected async openDetail(row: TableRow): Promise<void> {
    const build = this.detailFields();
    if (!build) return;
    const resolvePreview = this.resolvePreview();
    const preview = resolvePreview ? await resolvePreview(row) : null;
    const extract = this.onExtract();
    this.dialog.open(RecordDetailDialog, {
      width: 'min(680px, 94vw)',
      maxWidth: '94vw',
      autoFocus: false,
      data: {
        title: this.detailTitle()?.(row) ?? '',
        fields: build(row),
        preview,
        extract: extract ? () => extract(row) : null,
      },
    });
  }

  private async load(query: PageQuery): Promise<void> {
    const requestId = ++this.requestId;
    this.loading.set(true);
    this.error.set(null);
    try {
      const page = await this.fetchPage()(query);
      if (requestId !== this.requestId) return;
      this.rows.set(page.rows);
      this.total.set(page.total);
    } catch (error) {
      if (requestId !== this.requestId) return;
      this.rows.set([]);
      this.total.set(0);
      this.error.set(error instanceof Error ? error.message : String(error));
    } finally {
      if (requestId === this.requestId) this.loading.set(false);
    }
  }
}
