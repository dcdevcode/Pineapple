import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { FilesSection } from './files-section';
import { AnalysisService } from '../analysis.service';
import type { CaseSummary, Page } from '../analysis.models';
import type { FileRow } from '../analysis.models';

function summaryOf(over: Partial<CaseSummary> = {}): CaseSummary {
  return {
    title: 'X',
    device: {},
    source: {},
    parse: {},
    counts: {},
    is_encrypted: false,
    files_unlocked: true,
    ...over,
  };
}

function filePage(rows: Partial<FileRow>[]): Page<FileRow> {
  return {
    rows: rows.map((r) => ({
      file_id: 'id',
      domain: 'HomeDomain',
      relative_path: 'Library/SMS/sms.db',
      is_dir: 0,
      size: 2048,
      mtime: null,
      btime: null,
      target: null,
      ...r,
    })),
    total: rows.length,
    limit: 50,
    offset: 0,
  };
}

describe('FilesSection', () => {
  let files: ReturnType<typeof vi.fn>;
  let domains: ReturnType<typeof vi.fn>;
  const summary = signal<CaseSummary | null>(summaryOf());

  beforeEach(async () => {
    summary.set(summaryOf());
    files = vi.fn().mockResolvedValue(filePage([{}]));
    domains = vi.fn().mockResolvedValue([
      { domain: 'HomeDomain', count: 4 },
      { domain: 'AppDomain-com.x', count: 2 },
    ]);

    await TestBed.configureTestingModule({
      imports: [FilesSection],
      providers: [
        provideNoopAnimations(),
        {
          provide: AnalysisService,
          useValue: {
            files,
            domains,
            summary: summary.asReadonly(),
            previewFile: vi.fn().mockResolvedValue(null),
            extractFile: vi.fn().mockResolvedValue({ ok: true, path: '/tmp/x' }),
          },
        },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(FilesSection);
    await fixture.whenStable();
    return fixture;
  }

  it('loads domains and shows the size-formatted file rows', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;

    expect(domains).toHaveBeenCalled();
    expect(el.querySelectorAll('mat-option, [role="option"]').length).toBeGreaterThanOrEqual(0);
    const cells = Array.from(el.querySelectorAll('td')).map((c) => c.textContent?.trim());
    expect(cells).toContain('2.0 KB');
    expect(cells).toContain('file');
  });

  it('re-scopes the fetch when the domain changes', async () => {
    const fixture = await render();
    fixture.componentInstance['domain'].set('AppDomain-com.x');
    await fixture.whenStable();

    expect(files).toHaveBeenLastCalledWith(expect.objectContaining({ domain: 'AppDomain-com.x' }));
  });

  it('does not expose the Extract action while the backup is locked', async () => {
    summary.set(summaryOf({ is_encrypted: true, files_unlocked: false }));
    const fixture = await render();
    expect(fixture.componentInstance['onExtract']()).toBeNull();
  });
});
