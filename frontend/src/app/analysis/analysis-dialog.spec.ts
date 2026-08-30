import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialogRef } from '@angular/material/dialog';
import { AnalysisDialog } from './analysis-dialog';
import { AnalysisService } from './analysis.service';
import type { AnalysisProgress } from './analysis.models';

const IDLE: AnalysisProgress = {
  phase: 'idle',
  percent: 0,
  note: null,
  error: null,
  title: null,
  case_path: null,
  counts: {},
  skipped: [],
  running: false,
};

describe('AnalysisDialog', () => {
  const progress = signal<AnalysisProgress>(IDLE);
  let choosePineapple: ReturnType<typeof vi.fn>;
  let peek: ReturnType<typeof vi.fn>;
  let chooseCaseFolder: ReturnType<typeof vi.fn>;
  let startAnalysis: ReturnType<typeof vi.fn>;
  let dialogRef: { disableClose: boolean; close: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    progress.set(IDLE);
    choosePineapple = vi.fn().mockResolvedValue({ ok: true, path: '/x.pineapple' });
    peek = vi.fn().mockResolvedValue({
      ok: true,
      encrypted: false,
      device: { serial: 'S' },
      default_title: 'S',
    });
    chooseCaseFolder = vi.fn().mockResolvedValue({ ok: true, path: '/cases/x' });
    startAnalysis = vi.fn().mockResolvedValue({ ok: true });
    dialogRef = { disableClose: false, close: vi.fn() };

    const analysis = {
      progress: progress.asReadonly(),
      choosePineapple,
      peek,
      chooseCaseFolder,
      startAnalysis,
      cancelAnalysis: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [AnalysisDialog],
      providers: [
        provideNoopAnimations(),
        { provide: AnalysisService, useValue: analysis },
        { provide: MatDialogRef, useValue: dialogRef },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(AnalysisDialog);
    await fixture.whenStable();
    return fixture;
  }

  it('starts on the pick step', async () => {
    const fixture = await render();
    expect(fixture.componentInstance.step()).toBe('pick');
  });

  it('peeks the image and moves to configure', async () => {
    const fixture = await render();
    await fixture.componentInstance.chooseFile();

    expect(peek).toHaveBeenCalledWith('/x.pineapple');
    expect(fixture.componentInstance.step()).toBe('configure');
    expect(fixture.componentInstance.title()).toBe('S');
  });

  it('shows the peek error and stays on pick', async () => {
    peek.mockResolvedValue({ ok: false, error: 'not a zip' });
    const fixture = await render();
    await fixture.componentInstance.chooseFile();

    expect(fixture.componentInstance.step()).toBe('pick');
    expect(fixture.componentInstance.pickError()).toBe('not a zip');
  });

  it('requires a password only for an encrypted image', async () => {
    peek.mockResolvedValue({
      ok: true,
      encrypted: true,
      device: {},
      default_title: 'S',
    });
    const fixture = await render();
    await fixture.componentInstance.chooseFile();
    const component = fixture.componentInstance;

    expect(component.canStart()).toBe(false);
    component.password.set('secret');
    expect(component.canStart()).toBe(true);
  });

  it('stays on configure when the folder picker is cancelled', async () => {
    chooseCaseFolder.mockResolvedValue({ ok: false });
    const fixture = await render();
    await fixture.componentInstance.chooseFile();
    await fixture.componentInstance.start();

    expect(startAnalysis).not.toHaveBeenCalled();
    expect(fixture.componentInstance.step()).toBe('configure');
  });

  it('starts the parse and moves to progress', async () => {
    const fixture = await render();
    await fixture.componentInstance.chooseFile();
    await fixture.componentInstance.start();

    expect(startAnalysis).toHaveBeenCalledWith('/x.pineapple', '/cases/x', 'S', '');
    expect(fixture.componentInstance.step()).toBe('progress');
  });

  it('blocks closing while a phase is running, and shows the result on a terminal phase', async () => {
    const fixture = await render();
    fixture.componentInstance.step.set('progress');

    progress.set({ ...IDLE, phase: 'parsing', running: true });
    await fixture.whenStable();
    expect(dialogRef.disableClose).toBe(true);

    progress.set({ ...IDLE, phase: 'error', error: 'boom' });
    await fixture.whenStable();
    expect(dialogRef.disableClose).toBe(false);
    expect(fixture.componentInstance.step()).toBe('result');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('boom');
  });
});
