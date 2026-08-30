import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from './artifact-table';
import type { Page } from './analysis.models';

const dialog = { open: vi.fn() };

const COLUMNS: ColumnDef[] = [
  { key: 'name', label: 'Name' },
  { key: 'size', label: 'Size', numeric: true, format: (r) => `${r['size']} B` },
];

function pageOf(rows: TableRow[], total = rows.length): Page<TableRow> {
  return { rows, total, limit: 50, offset: 0 };
}

describe('ArtifactTable', () => {
  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [ArtifactTable],
      providers: [provideNoopAnimations(), { provide: MatDialog, useValue: dialog }],
    }).compileComponents();
  });

  async function render(fetchPage: FetchPage, extra: Record<string, unknown> = {}) {
    const fixture = TestBed.createComponent(ArtifactTable);
    fixture.componentRef.setInput('columns', COLUMNS);
    fixture.componentRef.setInput('fetchPage', fetchPage);
    for (const [key, value] of Object.entries(extra)) fixture.componentRef.setInput(key, value);
    await fixture.whenStable();
    return fixture;
  }

  it('renders rows from the fetch, applying column formatters', async () => {
    const fetch = vi.fn().mockResolvedValue(pageOf([{ name: 'a', size: 10 }]));
    const el = (await render(fetch)).nativeElement as HTMLElement;

    expect(fetch).toHaveBeenCalledWith(expect.objectContaining({ offset: 0 }));
    const cells = Array.from(el.querySelectorAll('td')).map((c) => c.textContent?.trim());
    expect(cells).toEqual(['a', '10 B']);
  });

  it('re-fetches with a new offset on page change', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(pageOf(new Array(50).fill({ name: 'x', size: 1 }), 200));
    const fixture = await render(fetch);

    fixture.componentInstance['onPage']({ pageIndex: 2, pageSize: 50, length: 200 });
    await fixture.whenStable();

    expect(fetch).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 100, limit: 50 }));
  });

  it('debounces search and resets to page 0', async () => {
    const fetch = vi.fn().mockResolvedValue(pageOf([]));
    const fixture = await render(fetch, { searchable: true });
    fixture.componentInstance['onPage']({ pageIndex: 3, pageSize: 50, length: 200 });
    await fixture.whenStable();

    fixture.componentInstance['onSearch']('hello');
    await new Promise((resolve) => setTimeout(resolve, 320));
    await fixture.whenStable();

    expect(fetch).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'hello', offset: 0 }));
  });

  it('shows the error state when the fetch rejects', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('No analysis is open.'));
    const el = (await render(fetch)).nativeElement as HTMLElement;
    expect(el.querySelector('.table__error')?.textContent).toContain('No analysis is open.');
  });

  it('shows the empty state', async () => {
    const el = (await render(vi.fn().mockResolvedValue(pageOf([])))).nativeElement as HTMLElement;
    expect(el.querySelector('.table__empty')).toBeTruthy();
  });

  it('opens the detail dialog on a row click when detailFields is set', async () => {
    const fetch = vi.fn().mockResolvedValue(pageOf([{ name: 'a', size: 10 }]));
    const fixture = await render(fetch, {
      detailFields: (row: TableRow) => [{ label: 'Name', value: String(row['name']) }],
    });
    (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    expect(dialog.open).toHaveBeenCalledOnce();
    expect(dialog.open.mock.calls[0][1].data.fields).toEqual([{ label: 'Name', value: 'a' }]);
  });

  it('does nothing on a row click without detailFields', async () => {
    const fetch = vi.fn().mockResolvedValue(pageOf([{ name: 'a', size: 10 }]));
    const fixture = await render(fetch);
    (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();
    expect(dialog.open).not.toHaveBeenCalled();
  });
});
