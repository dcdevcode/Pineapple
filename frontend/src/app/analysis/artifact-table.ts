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
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import type { Page, PageQuery } from './analysis.models';

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
