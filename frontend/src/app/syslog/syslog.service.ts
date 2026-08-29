import { Injectable, computed, signal } from '@angular/core';
import type { SyslogActionResult, SyslogLine, SyslogReadResult } from './syslog.models';

const POLL_INTERVAL_MS = 400;

/** Cap on lines kept in memory; the oldest are dropped past this. */
const MAX_LINES = 20_000;

/**
 * Drives one live syslog session over the pywebview bridge.
 *
 * `start()` asks the backend to open the stream, then polls `read_syslog()`
 * every {@link POLL_INTERVAL_MS} and appends the drained lines to {@link lines}.
 * Polling stops on its own when the backend reports the stream is no longer
 * running (device unplugged, connection dropped).
 *
 * `start()` and `stop()` are serialised: a close-then-reopen enqueues the stop
 * and the next start so the backend tears the connection down fully before it
 * reopens. When `window.pywebview` is absent (plain browser via `pnpm start`)
 * every method is an idle no-op.
 */
@Injectable({ providedIn: 'root' })
export class SyslogService {
  private readonly _lines = signal<SyslogLine[]>([]);
  private readonly _running = signal(false);
  private readonly _paused = signal(false);
  private readonly _error = signal<string | null>(null);
  /** Lines discarded since `start()` — backend buffer overflow + local cap. */
  private readonly _dropped = signal(0);

  readonly lines = this._lines.asReadonly();
  readonly running = this._running.asReadonly();
  readonly paused = this._paused.asReadonly();
  readonly error = this._error.asReadonly();
  readonly dropped = this._dropped.asReadonly();

  /** Distinct process names seen so far, for the process filter. */
  readonly processes = computed(() =>
    [...new Set(this._lines().map((line) => line.process))].sort((a, b) => a.localeCompare(b)),
  );

  private timer: ReturnType<typeof setInterval> | null = null;
  /** Bumped on every start/stop; a poll from an earlier session bails out. */
  private generation = 0;
  /** Serialises start/stop so their bridge calls never overlap. */
  private opChain: Promise<void> = Promise.resolve();

  start(): Promise<void> {
    return this.enqueue(() => this.runStart());
  }

  stop(): Promise<void> {
    return this.enqueue(() => this.runStop());
  }

  private enqueue(op: () => Promise<void>): Promise<void> {
    const next = this.opChain.then(op, op);
    this.opChain = next.catch(() => undefined);
    return next;
  }

  private async runStart(): Promise<void> {
    const api = window.pywebview?.api;
    if (!api) return;

    const generation = this.stopPolling();
    this.reset();

    let started: SyslogActionResult;
    try {
      started = await api.start_syslog();
    } catch (error) {
      started = { ok: false, error: String(error) };
    }
    if (generation !== this.generation) return; // superseded while awaiting

    if (!started.ok) {
      this._error.set(started.error ?? 'Could not start the syslog stream.');
      return;
    }

    this._running.set(true);
    this.timer = setInterval(() => void this.poll(generation), POLL_INTERVAL_MS);
  }

  private async runStop(): Promise<void> {
    this.stopPolling();
    this._running.set(false);
    this._paused.set(false);
    try {
      await window.pywebview?.api.stop_syslog();
    } catch {
      // Nothing actionable if the bridge is already gone.
    }
  }

  /** Stop the interval and invalidate in-flight polls. Returns the new generation. */
  private stopPolling(): number {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    return ++this.generation;
  }

  /** Toggle draining. While paused the backend buffer fills and eventually
   *  drops lines; the count surfaces via {@link dropped} on resume. */
  togglePause(): void {
    this._paused.update((paused) => !paused);
  }

  clear(): void {
    this._lines.set([]);
    this._dropped.set(0);
  }

  async export(content: string): Promise<SyslogActionResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false };
    try {
      return await api.save_syslog(content);
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  /** Run one poll cycle. Exposed so tests can await a single iteration. */
  async poll(generation = this.generation): Promise<void> {
    const api = window.pywebview?.api;
    if (!api || this._paused() || generation !== this.generation) return;

    let result: SyslogReadResult;
    try {
      result = await api.read_syslog();
    } catch (error) {
      this._error.set(String(error));
      return;
    }
    if (generation !== this.generation) return; // session ended while awaiting

    if (result.error) this._error.set(result.error);
    if (result.dropped) this._dropped.update((n) => n + result.dropped);
    if (result.lines.length) this.append(result.lines);

    if (!result.running) {
      this._running.set(false);
      this.stopPolling();
    }
  }

  private append(incoming: SyslogLine[]): void {
    this._lines.update((current) => {
      const next = current.concat(incoming);
      if (next.length > MAX_LINES) {
        const overflow = next.length - MAX_LINES;
        this._dropped.update((n) => n + overflow);
        return next.slice(overflow);
      }
      return next;
    });
  }

  private reset(): void {
    this._lines.set([]);
    this._dropped.set(0);
    this._error.set(null);
    this._paused.set(false);
    this._running.set(false);
  }
}
