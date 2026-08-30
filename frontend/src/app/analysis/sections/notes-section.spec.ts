import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { NotesSection } from './notes-section';
import { AnalysisService } from '../analysis.service';

describe('NotesSection', () => {
  const dialog = { open: vi.fn() };
  const notes = vi.fn().mockResolvedValue({
    rows: [{ rowid: 1, title: 'Groceries', folder: 'Notes', snippet: 's', body: 'full body' }],
    total: 1,
    limit: 50,
    offset: 0,
  });

  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [NotesSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { notes } },
      ],
    }).compileComponents();
  });

  it('renders note rows and opens the detail with the full body', async () => {
    const fixture = TestBed.createComponent(NotesSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('Groceries');
    el.querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    const data = dialog.open.mock.calls[0][1].data;
    expect(data.title).toBe('Groceries');
    expect(data.fields).toContainEqual({ label: 'Body', value: 'full body', long: true });
  });
});
