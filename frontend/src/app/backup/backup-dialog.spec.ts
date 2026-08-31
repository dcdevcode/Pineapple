import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { BackupDialog } from './backup-dialog';
import { BackupService } from './backup.service';
import type { BackupPreflight, BackupProgress } from './backup.models';

const IDLE: BackupProgress = {
  phase: 'idle',
  percent: 0,
  output_path: null,
  sha256: null,
  error: null,
  note: null,
  running: false,
};

describe('BackupDialog', () => {
  const progress = signal<BackupProgress>(IDLE);
  let preflight: BackupPreflight;
  let choosePath: ReturnType<typeof vi.fn>;
  let start: ReturnType<typeof vi.fn>;
  let cancel: ReturnType<typeof vi.fn>;
  let dialogRef: { disableClose: boolean; close: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    progress.set(IDLE);
    preflight = { ok: true, willEncrypt: false };
    choosePath = vi.fn().mockResolvedValue({ ok: true, path: '/tmp/x.pineapple' });
    start = vi.fn().mockResolvedValue({ ok: true });
    cancel = vi.fn().mockResolvedValue(undefined);
    dialogRef = { disableClose: false, close: vi.fn() };

    const backup = {
      progress: progress.asReadonly(),
      preflight: () => Promise.resolve(preflight),
      choosePath,
      start,
      cancel,
    };

    await TestBed.configureTestingModule({
      imports: [BackupDialog],
      providers: [
        provideNoopAnimations(),
        { provide: BackupService, useValue: backup },
        { provide: MatDialogRef, useValue: dialogRef },
        { provide: MAT_DIALOG_DATA, useValue: { deviceName: 'Test iPhone' } },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(BackupDialog);
    await fixture.whenStable();
    return fixture;
  }

  it('starts on the confirmation step', async () => {
    const fixture = await render();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('full backup of');
    expect(fixture.componentInstance.step()).toBe('confirm');
  });

  it('offers the encrypted / unencrypted choice when the device does not encrypt', async () => {
    const fixture = await render();
    fixture.componentInstance.toContinue();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    const values = Array.from(el.querySelectorAll('mat-radio-button input')).map((i) =>
      i.getAttribute('value'),
    );
    expect(values).toEqual(['encrypted', 'unencrypted']);
  });

  it('requires the existing password when the device already encrypts', async () => {
    preflight = { ok: true, willEncrypt: true };
    const fixture = await render();
    fixture.componentInstance.toContinue();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('mat-radio-group')).toBeNull();
    expect(el.textContent).toContain('already produces');

    const component = fixture.componentInstance;
    expect(component.canSubmit()).toBe(false);
    component.password.set('secret');
    expect(component.canSubmit()).toBe(true);
  });

  it('blocks submit until the two passwords match', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    component.toContinue();

    component.password.set('abc');
    component.passwordConfirm.set('abd');
    expect(component.canSubmit()).toBe(false);

    component.passwordConfirm.set('abc');
    expect(component.canSubmit()).toBe(true);
  });

  it('allows an unencrypted backup with no password', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    component.toContinue();
    component.encryptChoice.set('unencrypted');

    expect(component.canSubmit()).toBe(true);
  });

  it('stays on the options step when the save dialog is cancelled', async () => {
    choosePath.mockResolvedValue({ ok: false });
    const fixture = await render();
    const component = fixture.componentInstance;
    component.toContinue();
    component.encryptChoice.set('unencrypted');

    await component.createImage();

    expect(start).not.toHaveBeenCalled();
    expect(component.step()).toBe('options');
  });

  it('starts the acquisition and moves to the progress step', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    component.toContinue();
    component.password.set('pw');
    component.passwordConfirm.set('pw');

    await component.createImage();

    expect(start).toHaveBeenCalledWith('/tmp/x.pineapple', true, 'pw');
    expect(component.step()).toBe('progress');
  });

  it('shows the result and the saved path once the run is done', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    component.step.set('progress');

    progress.set({ ...IDLE, phase: 'done', output_path: '/tmp/x.pineapple' });
    await fixture.whenStable();

    expect(component.step()).toBe('result');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('/tmp/x.pineapple');
  });

  it('shows the SHA-256 on the result step and copies it', async () => {
    const digest = 'a'.repeat(64);
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    const fixture = await render();
    const component = fixture.componentInstance;
    component.step.set('progress');

    progress.set({
      ...IDLE,
      phase: 'done',
      output_path: '/tmp/x.pineapple',
      sha256: digest,
    });
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.backup__hash-value')?.textContent).toContain(digest);

    await component.copyHash();
    expect(writeText).toHaveBeenCalledWith(digest);
    expect(component.copied()).toBe(true);

    vi.unstubAllGlobals();
  });

  it('blocks closing the dialog while the acquisition is running', async () => {
    const fixture = await render();

    progress.set({ ...IDLE, phase: 'backing_up', running: true });
    await fixture.whenStable();
    expect(dialogRef.disableClose).toBe(true);

    progress.set({ ...IDLE, phase: 'done' });
    await fixture.whenStable();
    expect(dialogRef.disableClose).toBe(false);
  });
});
