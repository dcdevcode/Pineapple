import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { AccountsSection } from './accounts-section';
import { AnalysisService } from '../analysis.service';

describe('AccountsSection', () => {
  const dialog = { open: vi.fn() };
  const accounts = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        type: 'IMAP',
        identifier: 'AAAA-1111',
        description: 'Work mail',
        username: 'ada@example.com',
        added_utc: null,
        credential_type: 'com.apple.account.IMAP',
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  });

  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [AccountsSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { accounts } },
      ],
    }).compileComponents();
  });

  it('renders configured accounts and opens the detail dialog', async () => {
    const fixture = TestBed.createComponent(AccountsSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('ada@example.com');
    el.querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    const data = dialog.open.mock.calls[0][1].data;
    expect(data.title).toBe('Work mail');
    expect(data.fields).toContainEqual({ label: 'Type', value: 'IMAP', long: false });
  });
});
