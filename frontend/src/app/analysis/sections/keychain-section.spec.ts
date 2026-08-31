import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { KeychainSection } from './keychain-section';
import { AnalysisService } from '../analysis.service';

describe('KeychainSection', () => {
  const dialog = { open: vi.fn() };
  const keychain = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        item_class: 'genp',
        account: 'wifi-home',
        service: 'AirPort',
        server: null,
        access_group: 'apple',
        protection_class: 6,
        created_utc: null,
        modified_utc: null,
        secret: 'hunter2',
        secret_error: null,
      },
      {
        rowid: 2,
        item_class: 'inet',
        account: 'ada@example.com',
        service: null,
        server: 'mail.example.com',
        access_group: 'com.apple.mail',
        protection_class: 11,
        created_utc: null,
        modified_utc: null,
        secret: null,
        secret_error: 'keybag could not unwrap protection class 11',
      },
    ],
    total: 2,
    limit: 50,
    offset: 0,
  });

  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [KeychainSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { keychain } },
      ],
    }).compileComponents();
  });

  it('masks the secret in the table and shows it in the detail', async () => {
    const fixture = TestBed.createComponent(KeychainSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('AirPort');
    expect(el.textContent).not.toContain('hunter2');

    el.querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();
    const data = dialog.open.mock.calls[0][1].data;
    expect(data.fields).toContainEqual({ label: 'Secret', value: 'hunter2', long: true });
  });

  it('shows the error for an item that could not be decrypted', async () => {
    const fixture = TestBed.createComponent(KeychainSection);
    await fixture.whenStable();
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLElement>(
      'tr.mat-mdc-row',
    );

    rows[1].click();
    await fixture.whenStable();
    const data = dialog.open.mock.calls[0][1].data;
    expect(data.fields).toContainEqual({
      label: 'Secret unavailable',
      value: 'keybag could not unwrap protection class 11',
      long: false,
    });
  });
});
