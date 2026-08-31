import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { UnlockBanner } from './unlock-banner';
import { AnalysisService } from './analysis.service';
import type { CaseSummary } from './analysis.models';

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

describe('UnlockBanner', () => {
  const summary = signal<CaseSummary | null>(summaryOf());
  let unlock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    summary.set(summaryOf());
    unlock = vi.fn().mockResolvedValue({ ok: true });
    await TestBed.configureTestingModule({
      imports: [UnlockBanner],
      providers: [
        provideNoopAnimations(),
        { provide: AnalysisService, useValue: { summary: summary.asReadonly(), unlock } },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(UnlockBanner);
    await fixture.whenStable();
    return fixture;
  }

  it('stays hidden for a plain or already-unlocked case', async () => {
    const el = (await render()).nativeElement as HTMLElement;
    expect(el.querySelector('.unlock-banner')).toBeNull();

    summary.set(summaryOf({ is_encrypted: true, files_unlocked: true }));
    const el2 = (await render()).nativeElement as HTMLElement;
    expect(el2.querySelector('.unlock-banner')).toBeNull();
  });

  it('shows for a locked encrypted case and forwards the password', async () => {
    summary.set(summaryOf({ is_encrypted: true, files_unlocked: false }));
    const fixture = await render();
    expect((fixture.nativeElement as HTMLElement).querySelector('.unlock-banner')).toBeTruthy();

    fixture.componentInstance['password'].set('hunter2');
    await fixture.componentInstance['unlock']();
    expect(unlock).toHaveBeenCalledWith('hunter2');
  });

  it('surfaces a wrong-key error', async () => {
    unlock.mockResolvedValueOnce({ ok: false, error: 'Incorrect or missing backup password.' });
    summary.set(summaryOf({ is_encrypted: true, files_unlocked: false }));
    const fixture = await render();

    fixture.componentInstance['password'].set('nope');
    await fixture.componentInstance['unlock']();
    expect(fixture.componentInstance['unlockError']()).toContain('Incorrect');
  });
});
