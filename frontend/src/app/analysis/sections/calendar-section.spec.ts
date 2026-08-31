import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { CalendarSection } from './calendar-section';
import { AnalysisService } from '../analysis.service';

describe('CalendarSection', () => {
  const dialog = { open: vi.fn() };
  const calendar = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        title: 'Standup',
        calendar: 'Work',
        location: 'Room 4',
        notes: 'sync',
        start_utc: null,
        end_utc: null,
        all_day: 0,
        invitees: 'Ada; Grace',
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  });

  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [CalendarSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { calendar } },
      ],
    }).compileComponents();
  });

  it('renders events and opens the detail with the invitees', async () => {
    const fixture = TestBed.createComponent(CalendarSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('Standup');
    el.querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    const data = dialog.open.mock.calls[0][1].data;
    expect(data.title).toBe('Standup');
    expect(data.fields).toContainEqual({ label: 'Invitees', value: 'Ada; Grace', long: true });
  });
});
