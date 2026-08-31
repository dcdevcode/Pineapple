import { Injectable, signal } from '@angular/core';
import type {
  BackupActionResult,
  BackupPhase,
  BackupPreflight,
  BackupProgress,
} from './backup.models';

const POLL_INTERVAL_MS = 500;

const IDLE: BackupProgress = {
  phase: 'idle',
  percent: 0,
  output_path: null,
  sha256: null,
  error: null,
  note: null,
  running: false,
};

/**
 * Drives one `.pineapple` logical acquisition over the pywebview bridge.
 *
 * `start()` asks the backend to begin, then polls `read_backup_progress()` every
 * {@link POLL_INTERVAL_MS} into the {@link progress} signal until the backend
 * reports it is no longer running. `cancel()` asks the backend to stop; polling
 * continues until the run has fully unwound (so the UI can show the
 * "restoring encryption" step). Without `window.pywebview` every method is an
 * idle no-op.
 */
@Injectable({ providedIn: 'root' })
export class BackupService {
  private readonly _progress = signal<BackupProgress>(IDLE);
  readonly progress = this._progress.asReadonly();

  private timer: ReturnType<typeof setInterval> | null = null;
  /** Bumped on every start; a poll from an earlier run bails out. */
  private generation = 0;

  async preflight(): Promise<BackupPreflight> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false, error: 'The device bridge is not available.' };
    try {
      return await api.backup_preflight();
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  async choosePath(deviceName: string): Promise<BackupActionResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false };
    try {
      return await api.choose_backup_path(deviceName);
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  async start(path: string, encrypt: boolean, password: string): Promise<BackupActionResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false, error: 'The device bridge is not available.' };

    this.stopPolling();
    const generation = ++this.generation;
    this._progress.set({ ...IDLE, phase: 'preparing', running: true });

    let started: BackupActionResult;
    try {
      started = await api.start_backup(path, encrypt, password);
    } catch (error) {
      started = { ok: false, error: String(error) };
    }
    if (generation !== this.generation) return started;

    if (!started.ok) {
      this._progress.set({
        ...IDLE,
        phase: 'error',
        error: started.error ?? 'Could not start the acquisition.',
      });
      return started;
    }

    this.timer = setInterval(() => void this.poll(generation), POLL_INTERVAL_MS);
    void this.poll(generation);
    return started;
  }

  async cancel(): Promise<void> {
    const api = window.pywebview?.api;
    try {
      await api?.cancel_backup();
    } catch {
      // Nothing actionable if the bridge is already gone.
    }
  }

  /** Run one poll cycle. Exposed so tests can await a single iteration. */
  async poll(generation = this.generation): Promise<void> {
    const api = window.pywebview?.api;
    if (!api || generation !== this.generation) return;

    let result: BackupProgress;
    try {
      result = await api.read_backup_progress();
    } catch (error) {
      this._progress.update((current) => ({ ...current, error: String(error) }));
      return;
    }
    if (generation !== this.generation) return;

    this._progress.set(result);
    if (!result.running) this.stopPolling();
  }

  private stopPolling(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

/** Human label for a phase, for the progress view. */
export function phaseLabel(phase: BackupPhase): string {
  switch (phase) {
    case 'preparing':
      return 'Preparing the device…';
    case 'backing_up':
      return 'Backing up the device…';
    case 'packaging':
      return 'Packaging the .pineapple archive…';
    case 'hashing':
      return 'Computing the checksum…';
    case 'restoring_encryption':
      return 'Restoring the device settings…';
    case 'done':
      return 'Acquisition complete';
    case 'error':
      return 'Acquisition failed';
    case 'cancelled':
      return 'Acquisition cancelled';
    default:
      return '';
  }
}
