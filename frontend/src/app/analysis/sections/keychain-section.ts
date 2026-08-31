import { Component, inject } from '@angular/core';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery } from '../analysis.models';

/**
 * The Keychain section: item metadata for every entry, and the decrypted secret
 * when analysis recovered it. Secrets are decrypted once, at analysis time — a
 * row analysed without the backup password shows its `secret_error` instead, and
 * recovering it means re-analysing the image with the password.
 */
@Component({
  selector: 'app-keychain-section',
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
export class KeychainSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'item_class', label: 'Class' },
    { key: 'service', label: 'Service' },
    { key: 'server', label: 'Server' },
    { key: 'account', label: 'Account' },
    { key: 'secret', label: 'Secret', format: (r) => (r['secret'] ? '••••••' : '') },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.keychain(q)) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('Class', r['item_class']),
    ...field('Account', r['account']),
    ...field('Service', r['service']),
    ...field('Server', r['server']),
    ...field('Access group', r['access_group']),
    ...field('Protection class', r['protection_class']),
    ...field('Created', localTime(r['created_utc'])),
    ...field('Modified', localTime(r['modified_utc'])),
    ...field('Secret', r['secret'], true),
    ...field('Secret unavailable', r['secret_error']),
  ];

  protected readonly title = (r: TableRow): string =>
    String(r['service'] || r['server'] || r['account'] || 'Keychain item');
}
