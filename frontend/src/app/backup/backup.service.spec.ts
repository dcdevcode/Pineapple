import { TestBed } from '@angular/core/testing';
import { BackupService, phaseLabel } from './backup.service';
import type { BackupProgress } from './backup.models';
import type { PineappleApi } from '../device/pywebview';

function useBridge(api: Partial<PineappleApi>): void {
  window.pywebview = { api: api as PineappleApi };
}

const POLL_INTERVAL_WINDOW = 700;

function progress(overrides: Partial<BackupProgress> = {}): BackupProgress {
  return {
    phase: 'backing_up',
    percent: 0,
    output_path: null,
    error: null,
    note: null,
    running: true,
    ...overrides,
  };
}

function makeApi() {
  return {
    backup_preflight: vi.fn().mockResolvedValue({ ok: true, willEncrypt: false }),
    choose_backup_path: vi.fn().mockResolvedValue({ ok: true, path: '/tmp/x.pineapple' }),
    start_backup: vi.fn().mockResolvedValue({ ok: true }),
    read_backup_progress: vi.fn().mockResolvedValue(progress()),
    cancel_backup: vi.fn().mockResolvedValue({ ok: true }),
  };
}

describe('BackupService', () => {
  let service: BackupService;

  beforeEach(() => {
    service = TestBed.inject(BackupService);
  });

  afterEach(() => {
    delete window.pywebview;
    vi.useRealTimers();
  });

  it('is an idle no-op without the pywebview bridge', async () => {
    expect(await service.preflight()).toEqual({
      ok: false,
      error: 'The device bridge is not available.',
    });
    expect(await service.start('/tmp/x', false, '')).toEqual({
      ok: false,
      error: 'The device bridge is not available.',
    });
    expect(service.progress().phase).toBe('idle');
  });

  it('passes the pre-flight result through', async () => {
    const api = makeApi();
    api.backup_preflight.mockResolvedValue({ ok: true, willEncrypt: true });
    useBridge(api);

    expect(await service.preflight()).toEqual({ ok: true, willEncrypt: true });
  });

  it('starts the backup and polls progress into the signal', async () => {
    const api = makeApi();
    api.read_backup_progress.mockResolvedValue(progress({ percent: 42 }));
    useBridge(api);

    await service.start('/tmp/x.pineapple', true, 'pw');

    expect(api.start_backup).toHaveBeenCalledWith('/tmp/x.pineapple', true, 'pw');
    expect(service.progress().phase).toBe('backing_up');
    expect(service.progress().percent).toBe(42);
  });

  it('stops polling once the backend reports the run finished', async () => {
    vi.useFakeTimers();
    const api = makeApi();
    api.read_backup_progress.mockResolvedValue(
      progress({ phase: 'done', running: false, output_path: '/tmp/x.pineapple' }),
    );
    useBridge(api);

    await service.start('/tmp/x.pineapple', false, '');
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_WINDOW);
    const calls = api.read_backup_progress.mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_WINDOW * 3);

    expect(api.read_backup_progress.mock.calls.length).toBe(calls);
    expect(service.progress().phase).toBe('done');
  });

  it('surfaces a refused start', async () => {
    const api = makeApi();
    api.start_backup.mockResolvedValue({ ok: false, error: 'no single device connected' });
    useBridge(api);

    const result = await service.start('/tmp/x', false, '');

    expect(result.ok).toBe(false);
    expect(service.progress().phase).toBe('error');
    expect(service.progress().error).toBe('no single device connected');
  });

  it('asks the backend to cancel', async () => {
    const api = makeApi();
    useBridge(api);

    await service.cancel();

    expect(api.cancel_backup).toHaveBeenCalled();
  });

  it('labels each phase', () => {
    expect(phaseLabel('backing_up')).toContain('Backing up');
    expect(phaseLabel('done')).toContain('complete');
    expect(phaseLabel('idle')).toBe('');
  });
});
