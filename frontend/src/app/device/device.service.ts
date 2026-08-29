import { Injectable, signal } from '@angular/core';
import type { DeviceInfoResult, DevicePresence, DeviceState } from './device.models';

const POLL_INTERVAL_MS = 2000;

/**
 * Watches for a USB device via the pywebview bridge and exposes its state.
 *
 * Every {@link POLL_INTERVAL_MS} it asks the backend whether a device is
 * attached (a cheap, daemon-only call). The full device info is fetched only
 * once per device — except while the device is `unpaired`, where every poll
 * retries so granting "Trust this computer" is picked up without replugging.
 *
 * When `window.pywebview` is absent (the app running in a plain browser via
 * `pnpm start`) the service stays idle and never polls.
 */
@Injectable({ providedIn: 'root' })
export class DeviceService {
  private readonly _state = signal<DeviceState>({ status: 'idle' });
  readonly state = this._state.asReadonly();

  private timer: ReturnType<typeof setInterval> | null = null;
  private readyListener: (() => void) | null = null;

  /** UDID currently reflected in `_state` (null while idle). */
  private currentUdid: string | null = null;
  /** Bumped on every info fetch and whenever the device disappears; a late
   *  `get_device_info` whose id no longer matches is ignored. */
  private infoRequestId = 0;

  /** Begin watching. Safe to call more than once. */
  start(): void {
    if (this.timer !== null || this.readyListener !== null) return;

    if (window.pywebview?.api) {
      this.beginPolling();
      return;
    }

    // The bridge may not be injected yet; wait for pywebview to announce itself.
    const listener = () => {
      this.readyListener = null;
      this.beginPolling();
    };
    this.readyListener = listener;
    window.addEventListener('pywebviewready', listener, { once: true });
  }

  /** Stop watching and release the timer / event listener. */
  stop(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.readyListener !== null) {
      window.removeEventListener('pywebviewready', this.readyListener);
      this.readyListener = null;
    }
  }

  private beginPolling(): void {
    void this.refresh();
    this.timer = setInterval(() => void this.refresh(), POLL_INTERVAL_MS);
  }

  /** Run one poll cycle. Exposed so tests can await a single iteration. */
  async refresh(): Promise<void> {
    const api = window.pywebview?.api;
    if (!api) return;

    let presence: DevicePresence;
    try {
      presence = await api.connected_device();
    } catch {
      presence = { status: 'none' };
    }

    if (presence.status !== 'one') {
      this.showDeviceless(presence.status === 'multiple' ? 'multiple' : 'idle');
      return;
    }

    const device = presence.device;
    const isNewDevice = device.Udid !== this.currentUdid;
    const retryingUnpaired = this._state().status === 'unpaired';
    if (!isNewDevice && !retryingUnpaired) return;

    this.currentUdid = device.Udid;
    if (isNewDevice) {
      this._state.set({ status: 'connecting', udid: device.Udid });
    }

    const requestId = ++this.infoRequestId;
    let result: DeviceInfoResult;
    try {
      result = await api.get_device_info(device.Udid);
    } catch (error) {
      result = { ok: false, error: String(error) };
    }
    if (requestId !== this.infoRequestId) return; // superseded or disconnected

    if (!result.ok || !result.info) {
      this._state.set({
        status: 'unpaired',
        udid: device.Udid,
        error: result.error ?? 'Device information is not available.',
      });
      return;
    }

    const name = String(result.info['DeviceName'] ?? 'Apple device');
    this._state.set({ status: 'ready', udid: device.Udid, name, info: result.info });
  }

  /** Move to a state with no single device, cancelling any in-flight fetch. */
  private showDeviceless(status: 'idle' | 'multiple'): void {
    if (this.currentUdid !== null) {
      this.currentUdid = null;
      this.infoRequestId++;
    }
    if (this._state().status !== status) {
      this._state.set({ status });
    }
  }
}
