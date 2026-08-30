import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { ArtifactTable, type ColumnDef, type FetchPage } from '../artifact-table';
import { AnalysisService } from '../analysis.service';
import type { DomainCount, Page, PageQuery } from '../analysis.models';
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

/** The Files section: the file index, filterable by domain and path. */
@Component({
  selector: 'app-files-section',
  imports: [ArtifactTable, FormsModule, MatFormFieldModule, MatSelectModule],
  templateUrl: './files-section.html',
  styleUrl: './files-section.scss',
})
export class FilesSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly domain = signal('');
  protected readonly domains = signal<DomainCount[]>([]);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'domain', label: 'Domain' },
    { key: 'relative_path', label: 'Path' },
    {
      key: 'is_dir',
      label: 'Kind',
      format: (row) => (row['target'] ? 'symlink' : row['is_dir'] ? 'dir' : 'file'),
    },
    { key: 'size', label: 'Size', numeric: true, format: (row) => formatSize(row['size']) },
  ];

  protected readonly fetch: FetchPage = async (query: PageQuery) => {
    const page = await this.analysis.files({
      ...query,
      domain: this.domain() || undefined,
    });
    return page as unknown as Page<TableRow>;
  };

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
