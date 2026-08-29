import { TestBed } from '@angular/core/testing';
import { SyslogService } from './syslog.service';
import type { SyslogLine } from './syslog.models';
import type { PineappleApi } from '../device/pywebview';

/** Install a partial bridge for the test (real one has more methods). */
function useBridge(api: Partial<PineappleApi>): void {
  window.pywebview = { api: api as PineappleApi };
}

/** A little more than one poll interval, for fake-timer advancement. */
const POLL_INTERVAL_WINDOW = 600;

function line(overrides: Partial<SyslogLine> = {}): SyslogLine {
  return {
    timestamp: '2026-08-29T12:00:00',
    process: 'SpringBoard',
    pid: 62,
    level: 'NOTICE',
    label: null,
    message: 'hello',
    ...overrides,
  };
}

function makeApi() {
  return {
    start_syslog: vi.fn().mockResolvedValue({ ok: true }),
    read_syslog: vi.fn().mockResolvedValue({ lines: [], dropped: 0, running: true, error: null }),
    stop_syslog: vi.fn().mockResolvedValue({ ok: true }),
    save_syslog: vi.fn().mockResolvedValue({ ok: true, path: '/tmp/syslog.txt' }),
  };
}

describe('SyslogService', () => {
  let service: SyslogService;

  beforeEach(() => {
    service = TestBed.inject(SyslogService);
  });

  afterEach(async () => {
    await service.stop();
    delete window.pywebview;
    vi.useRealTimers();
  });

  it('does nothing without the pywebview bridge', async () => {
    await service.start();
    expect(service.running()).toBe(false);
    expect(service.lines()).toEqual([]);
  });

  it('surfaces a refused start', async () => {
    const api = makeApi();
    api.start_syslog.mockResolvedValue({ ok: false, error: 'no single device connected' });
    useBridge(api);

    await service.start();

    expect(service.running()).toBe(false);
    expect(service.error()).toBe('no single device connected');
  });

  it('accumulates drained lines and tracks dropped', async () => {
    const api = makeApi();
    api.read_syslog
      .mockResolvedValueOnce({
        lines: [line({ message: 'a' })],
        dropped: 0,
        running: true,
        error: null,
      })
      .mockResolvedValue({
        lines: [line({ message: 'b' })],
        dropped: 3,
        running: true,
        error: null,
      });
    useBridge(api);

    await service.start();
    await service.poll();
    await service.poll();

    expect(service.lines().map((l) => l.message)).toEqual(['a', 'b']);
    expect(service.dropped()).toBe(3);
  });

  it('stops polling once the backend reports the stream ended', async () => {
    vi.useFakeTimers();
    const api = makeApi();
    api.read_syslog.mockResolvedValue({
      lines: [],
      dropped: 0,
      running: false,
      error: 'device disconnected',
    });
    useBridge(api);

    await service.start();
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_WINDOW);
    const calls = api.read_syslog.mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_WINDOW * 3);

    expect(api.read_syslog.mock.calls.length).toBe(calls);
    expect(service.running()).toBe(false);
    expect(service.error()).toBe('device disconnected');
  });

  it('does not drain while paused', async () => {
    const api = makeApi();
    api.read_syslog.mockResolvedValue({ lines: [line()], dropped: 0, running: true, error: null });
    useBridge(api);

    await service.start();
    service.togglePause();
    await service.poll();

    expect(service.lines()).toEqual([]);
  });

  it('exposes distinct process names sorted', async () => {
    const api = makeApi();
    api.read_syslog.mockResolvedValue({
      lines: [
        line({ process: 'kernel' }),
        line({ process: 'SpringBoard' }),
        line({ process: 'kernel' }),
      ],
      dropped: 0,
      running: true,
      error: null,
    });
    useBridge(api);

    await service.start();
    await service.poll();

    expect(service.processes()).toEqual(['kernel', 'SpringBoard']);
  });

  it('stops the stream on stop()', async () => {
    const api = makeApi();
    useBridge(api);

    await service.start();
    await service.stop();

    expect(api.stop_syslog).toHaveBeenCalled();
    expect(service.running()).toBe(false);
  });

  it('streams again after a stop / start cycle (dialog reopen)', async () => {
    const api = makeApi();
    api.read_syslog.mockResolvedValue({
      lines: [line({ message: 'x' })],
      dropped: 0,
      running: true,
      error: null,
    });
    useBridge(api);

    await service.start();
    await service.poll();
    await service.stop();

    await service.start();
    expect(service.running()).toBe(true);
    await service.poll();

    expect(service.lines().map((l) => l.message)).toEqual(['x']);
    expect(api.start_syslog).toHaveBeenCalledTimes(2);
  });

  it('a stale poll from the previous session cannot stop the new one', async () => {
    const api = makeApi();
    let release!: (r: unknown) => void;
    api.read_syslog.mockImplementationOnce(() => new Promise((resolve) => (release = resolve)));
    useBridge(api);

    await service.start();
    const stalePoll = service.poll(); // in flight against session 1

    await service.stop();
    await service.start(); // session 2

    // Session 1's read resolves late, reporting the stream had ended.
    release({ lines: [], dropped: 0, running: false, error: null });
    await stalePoll;

    expect(service.running()).toBe(true);
  });
});
