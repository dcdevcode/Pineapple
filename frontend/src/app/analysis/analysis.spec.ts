import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { Analysis } from './analysis';
import { AnalysisService } from './analysis.service';
import type { CaseSummary } from './analysis.models';

const SUMMARY: CaseSummary = {
  title: 'F17ABC123',
  device: {
    device_name: 'Test iPhone',
    product_name: 'iPhone 13',
    product_version: '17.5.1',
    serial: 'F17ABC123',
  },
  source: { path: '/x.pineapple', sha256: 'abc', is_encrypted: false },
  parse: { status: 'done', counts: { messages: 3 }, skipped: [] },
  counts: { apps: 1, files: 5, messages: 3, calls: 3, contacts: 2 },
  is_encrypted: false,
  files_unlocked: true,
};

describe('Analysis', () => {
  const summary = signal<CaseSummary | null>(null);
  const dialog = { open: vi.fn() };
  let chooseCaseFolder: ReturnType<typeof vi.fn>;
  let openCase: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    summary.set(null);
    dialog.open.mockClear();
    chooseCaseFolder = vi.fn().mockResolvedValue({ ok: true, path: '/cases/x' });
    openCase = vi.fn().mockImplementation(async () => {
      summary.set(SUMMARY);
      return { ok: true };
    });

    const emptyPage = { rows: [], total: 0, limit: 50, offset: 0 };
    const analysis = {
      summary: summary.asReadonly(),
      chooseCaseFolder,
      openCase,
      closeCase: () => summary.set(null),
      domains: vi.fn().mockResolvedValue([]),
      apps: vi.fn().mockResolvedValue([]),
      notes: vi.fn().mockResolvedValue(emptyPage),
      photos: vi.fn().mockResolvedValue(emptyPage),
      photoAlbums: vi.fn().mockResolvedValue(emptyPage),
      calendar: vi.fn().mockResolvedValue(emptyPage),
      voicemail: vi.fn().mockResolvedValue(emptyPage),
      deviceUsage: vi.fn().mockResolvedValue(emptyPage),
      accounts: vi.fn().mockResolvedValue(emptyPage),
      safariHistory: vi.fn().mockResolvedValue(emptyPage),
      safariBookmarks: vi.fn().mockResolvedValue(emptyPage),
      whatsappChats: vi.fn().mockResolvedValue(emptyPage),
      whatsappMessages: vi.fn().mockResolvedValue(emptyPage),
      previewFile: vi.fn().mockResolvedValue(null),
      extractFile: vi.fn().mockResolvedValue({ ok: true, path: '/x' }),
    };

    await TestBed.configureTestingModule({
      imports: [Analysis],
      providers: [
        provideNoopAnimations(),
        { provide: AnalysisService, useValue: analysis },
        { provide: MatDialog, useValue: dialog },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(Analysis);
    await fixture.whenStable();
    return fixture;
  }

  it('shows the launcher when no case is open', async () => {
    const el = (await render()).nativeElement as HTMLElement;
    expect(el.querySelector('.analysis--launcher')).toBeTruthy();
    expect(el.textContent).toContain('New analysis');
  });

  it('opens the dialog from "New analysis"', async () => {
    const el = (await render()).nativeElement as HTMLElement;
    const button = Array.from(el.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('New analysis'),
    )!;
    button.click();
    expect(dialog.open).toHaveBeenCalledOnce();
  });

  it('opens an existing case folder', async () => {
    const fixture = await render();
    await fixture.componentInstance.openExisting();
    await fixture.whenStable();

    expect(chooseCaseFolder).toHaveBeenCalled();
    expect(openCase).toHaveBeenCalledWith('/cases/x');
    expect((fixture.nativeElement as HTMLElement).querySelector('.analysis--browser')).toBeTruthy();
  });

  it('renders the browser and switches sections when a case is open', async () => {
    summary.set(SUMMARY);
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('.analysis__title')?.textContent?.trim()).toBe('F17ABC123');
    expect(el.textContent).toContain('iOS 17.5.1');
    expect(el.querySelector('app-analysis-overview')).toBeTruthy();

    fixture.componentInstance['active'].set('files');
    await fixture.whenStable();
    expect(el.querySelector('app-files-section')).toBeTruthy();
  });

  it('lists the Notes / Safari / WhatsApp sections and renders them', async () => {
    summary.set(SUMMARY);
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    const labels = Array.from(el.querySelectorAll('.analysis__nav-label')).map((n) =>
      n.textContent?.trim(),
    );
    expect(labels).toEqual(
      expect.arrayContaining([
        'Notes',
        'Photos',
        'Calendar',
        'Voicemail',
        'Usage',
        'Accounts',
        'Safari',
        'WhatsApp',
      ]),
    );

    fixture.componentInstance['active'].set('whatsapp');
    await fixture.whenStable();
    expect(el.querySelector('app-whatsapp-section')).toBeTruthy();

    fixture.componentInstance['active'].set('photos');
    await fixture.whenStable();
    expect(el.querySelector('app-photos-section')).toBeTruthy();

    fixture.componentInstance['active'].set('calendar');
    await fixture.whenStable();
    expect(el.querySelector('app-calendar-section')).toBeTruthy();

    fixture.componentInstance['active'].set('accounts');
    await fixture.whenStable();
    expect(el.querySelector('app-accounts-section')).toBeTruthy();
  });

  it('returns to the launcher on "Close analysis"', async () => {
    summary.set(SUMMARY);
    const fixture = await render();
    fixture.componentInstance.close();
    await fixture.whenStable();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.analysis--launcher'),
    ).toBeTruthy();
  });
});
