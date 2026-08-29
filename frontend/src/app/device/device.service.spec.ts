import { TestBed } from '@angular/core/testing';
import { DeviceService } from './device.service';
import type { DeviceInfo } from './device.models';

/** A little more than one poll interval, for fake-timer advancement. */
const POLL_INTERVAL_WINDOW = 2500;

const SAMPLE_INFO: DeviceInfo = {
  DeviceName: 'Test iPhone',
  ProductVersion: '18.5',
  TotalDiskCapacity: 128_000_000_000,
  PasswordProtected: true,
};

function makeApi() {
  return {
    list_devices: vi.fn().mockResolvedValue([]),
    get_device_info: vi.fn().mockResolvedValue({ ok: true, info: SAMPLE_INFO }),
  };
}

function connected(udid = 'A') {
  return [{ Udid: udid, ConnectionType: 'USB' }];
}

describe('DeviceService', () => {
  let service: DeviceService;

  beforeEach(() => {
    service = TestBed.inject(DeviceService);
  });

  afterEach(() => {
    service.stop();
    delete window.pywebview;
    vi.useRealTimers();
  });

  it('stays idle and never polls without the pywebview bridge', () => {
    vi.useFakeTimers();
    service.start();
    vi.advanceTimersByTime(10_000);
    expect(service.state()).toEqual({ status: 'idle' });
  });

  it('stays idle when no device is connected', async () => {
    window.pywebview = { api: makeApi() };
    await service.refresh();
    expect(service.state().status).toBe('idle');
  });

  it('reaches "ready" with the device name and info', async () => {
    const api = makeApi();
    api.list_devices.mockResolvedValue(connected());
    window.pywebview = { api };

    await service.refresh();

    expect(service.state()).toEqual({
      status: 'ready',
      udid: 'A',
      name: 'Test iPhone',
      info: SAMPLE_INFO,
    });
  });

  it('fetches the device info only once per device', async () => {
    const api = makeApi();
    api.list_devices.mockResolvedValue(connected());
    window.pywebview = { api };

    await service.refresh();
    await service.refresh();
    await service.refresh();

    expect(api.get_device_info).toHaveBeenCalledTimes(1);
  });

  it('retries while unpaired and flips to ready once trusted', async () => {
    const api = makeApi();
    api.list_devices.mockResolvedValue(connected());
    api.get_device_info.mockResolvedValueOnce({ ok: false, error: 'Not trusted' });
    window.pywebview = { api };

    await service.refresh();
    expect(service.state()).toMatchObject({ status: 'unpaired', error: 'Not trusted' });

    await service.refresh();
    expect(service.state().status).toBe('ready');
    expect(api.get_device_info).toHaveBeenCalledTimes(2);
  });

  it('returns to idle on disconnect and re-fetches on reconnect', async () => {
    const api = makeApi();
    api.list_devices.mockResolvedValue(connected());
    window.pywebview = { api };
    await service.refresh();

    api.list_devices.mockResolvedValue([]);
    await service.refresh();
    expect(service.state().status).toBe('idle');

    api.list_devices.mockResolvedValue(connected());
    await service.refresh();
    expect(service.state().status).toBe('ready');
    expect(api.get_device_info).toHaveBeenCalledTimes(2);
  });

  it('follows a device swap', async () => {
    const api = makeApi();
    api.list_devices.mockResolvedValue(connected('A'));
    window.pywebview = { api };
    await service.refresh();

    api.list_devices.mockResolvedValue(connected('B'));
    await service.refresh();

    expect(api.get_device_info).toHaveBeenLastCalledWith('B');
    expect(service.state()).toMatchObject({ status: 'ready', udid: 'B' });
  });

  it('ignores a stale info result that resolves after a disconnect', async () => {
    const api = makeApi();
    api.list_devices.mockResolvedValue(connected());
    let resolveInfo!: (value: unknown) => void;
    api.get_device_info.mockReturnValue(new Promise((resolve) => (resolveInfo = resolve)));
    window.pywebview = { api };

    const pending = service.refresh();
    api.list_devices.mockResolvedValue([]);
    await service.refresh();

    resolveInfo({ ok: true, info: SAMPLE_INFO });
    await pending;

    expect(service.state().status).toBe('idle');
  });

  it('treats a list_devices rejection as no device', async () => {
    const api = makeApi();
    api.list_devices.mockRejectedValue(new Error('bridge down'));
    window.pywebview = { api };

    await service.refresh();

    expect(service.state().status).toBe('idle');
  });

  it('stops polling after stop()', async () => {
    vi.useFakeTimers();
    const api = makeApi();
    window.pywebview = { api };

    service.start();
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_WINDOW);
    const callsBeforeStop = api.list_devices.mock.calls.length;

    service.stop();
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_WINDOW * 3);

    expect(api.list_devices.mock.calls.length).toBe(callsBeforeStop);
  });
});
