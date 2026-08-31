import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { UsageSection } from './usage-section';
import { AnalysisService } from '../analysis.service';

describe('UsageSection', () => {
  const dialog = { open: vi.fn() };
  const deviceUsage = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        stream: '/app/usage',
        bundle_id: 'com.apple.mobilesafari',
        value: null,
        start_utc: null,
        end_utc: null,
        duration_seconds: 90,
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  });

  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [UsageSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { deviceUsage } },
      ],
    }).compileComponents();
  });

  it('renders knowledgeC events and opens the detail dialog', async () => {
    const fixture = TestBed.createComponent(UsageSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('com.apple.mobilesafari');
    el.querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    const data = dialog.open.mock.calls[0][1].data;
    expect(data.fields).toContainEqual({ label: 'Duration', value: '1:30', long: false });
  });
});
