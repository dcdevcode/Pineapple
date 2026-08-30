import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { SafariSection } from './safari-section';
import { AnalysisService } from '../analysis.service';

describe('SafariSection', () => {
  const emptyPage = { rows: [], total: 0, limit: 50, offset: 0 };
  const safariHistory = vi.fn().mockResolvedValue({
    rows: [{ rowid: 1, url: 'https://a.test/', title: 'A', visit_utc: null, visit_count: 2 }],
    total: 1,
    limit: 50,
    offset: 0,
  });
  const safariBookmarks = vi.fn().mockResolvedValue(emptyPage);
  const dialog = { open: vi.fn() };

  beforeEach(async () => {
    safariHistory.mockClear();
    safariBookmarks.mockClear();
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [SafariSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { safariHistory, safariBookmarks } },
      ],
    }).compileComponents();
  });

  function headers(fixture: { nativeElement: unknown }): (string | undefined)[] {
    return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('th')).map((th) =>
      th.textContent?.trim(),
    );
  }

  it('shows history first and switches to bookmarks', async () => {
    const fixture = TestBed.createComponent(SafariSection);
    await fixture.whenStable();

    expect(safariHistory).toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('https://a.test/');

    fixture.componentInstance['view'].set('bookmarks');
    await fixture.whenStable();
    expect(safariBookmarks).toHaveBeenCalled();
  });

  it('swaps the column set when the view changes', async () => {
    const fixture = TestBed.createComponent(SafariSection);
    await fixture.whenStable();
    expect(headers(fixture)).toEqual(['Visited', 'Title', 'URL', 'Visits']);

    fixture.componentInstance['view'].set('bookmarks');
    await fixture.whenStable();
    expect(headers(fixture)).toEqual(['Folder', 'Title', 'URL']);
  });

  it('opens the row-detail dialog for a history row', async () => {
    const fixture = TestBed.createComponent(SafariSection);
    await fixture.whenStable();

    (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>('tr[mat-row]')!.click();
    await fixture.whenStable();
    expect(dialog.open).toHaveBeenCalled();
  });
});
