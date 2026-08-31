import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { ArtifactTable, type ColumnDef, type FetchPage } from '../artifact-table';
import { AnalysisService } from '../analysis.service';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { DomainCount, FilePreview, Page, PageQuery } from '../analysis.models';
import type { TableRow } from '../artifact-table';

function formatSize(bytes: unknown): string {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return '';
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = n / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

function fileKind(row: TableRow): string {
  return row['target'] ? 'symlink' : row['is_dir'] ? 'dir' : 'file';
}

/** The Files section: the file index, filterable by domain and path. A row opens
 *  its full metadata plus a content preview and an Extract action; for an
 *  encrypted backup those need the decryption key (supplied via the shared
 *  unlock banner in the case-browser shell). */
@Component({
  selector: 'app-files-section',
  imports: [ArtifactTable, FormsModule, MatFormFieldModule, MatSelectModule],
  templateUrl: './files-section.html',
  styleUrl: './files-section.scss',
})
export class FilesSection {
  private readonly analysis = inject(AnalysisService);

  private readonly summary = this.analysis.summary;
  protected readonly domain = signal('');
  protected readonly domains = signal<DomainCount[]>([]);

  private readonly locked = computed(
    () => !!this.summary()?.is_encrypted && !this.summary()?.files_unlocked,
  );

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'domain', label: 'Domain' },
    { key: 'relative_path', label: 'Path' },
    { key: 'is_dir', label: 'Kind', format: fileKind },
    { key: 'size', label: 'Size', numeric: true, format: (row) => formatSize(row['size']) },
  ];

  protected readonly fetch: FetchPage = async (query: PageQuery) => {
    const page = await this.analysis.files({
      ...query,
      domain: this.domain() || undefined,
    });
    return page as unknown as Page<TableRow>;
  };

  protected readonly detail: DetailBuilder = (row) => [
    ...field('Path', row['relative_path'], true),
    ...field('Domain', row['domain']),
    ...field('Kind', fileKind(row)),
    ...field('Size', formatSize(row['size']) || '0 B'),
    ...field('Modified', localTime(row['mtime'])),
    ...field('Created', localTime(row['btime'])),
    ...field('Symlink target', row['target']),
    ...field('File ID', row['file_id']),
  ];

  protected readonly title = (row: TableRow): string =>
    String(row['relative_path']).split('/').pop() || String(row['relative_path']);

  protected readonly resolvePreview = (row: TableRow): Promise<FilePreview | null> =>
    this.analysis.previewFile(String(row['file_id']));

  /** Null while locked so the dialog hides the Extract button. */
  protected readonly onExtract = computed(() =>
    this.locked() ? null : (row: TableRow) => this.analysis.extractFile(String(row['file_id'])),
  );

  constructor() {
    void this.loadDomains();
  }

  private async loadDomains(): Promise<void> {
    try {
      this.domains.set(await this.analysis.domains());
    } catch {
      this.domains.set([]);
    }
  }
}
