import { Component, inject } from '@angular/core';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

/** The Accounts section: mail / social / iCloud accounts configured on the
 *  device (metadata only — credentials live in the keychain). */
@Component({
  selector: 'app-accounts-section',
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
export class AccountsSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'type', label: 'Type' },
    { key: 'description', label: 'Description' },
    { key: 'username', label: 'Username' },
    { key: 'added_utc', label: 'Added', format: (r) => localTime(r['added_utc']) },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.accounts(q)) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('Type', r['type']),
    ...field('Description', r['description']),
    ...field('Username', r['username']),
    ...field('Identifier', r['identifier']),
    ...field('Credential type', r['credential_type']),
    ...field('Added', localTime(r['added_utc'])),
  ];

  protected readonly title = (r: TableRow): string =>
    String(r['description'] || r['username'] || r['type'] || 'Account');
}
