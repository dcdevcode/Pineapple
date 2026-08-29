import type { DevicePresence, DeviceInfoResult } from './device.models';

/** The Python `Api` object, exposed by pywebview as `window.pywebview.api`. */
export interface PineappleApi {
  connected_device(): Promise<DevicePresence>;
  get_device_info(udid: string): Promise<DeviceInfoResult>;
}

declare global {
  interface Window {
    /** Injected by pywebview only when running inside the desktop shell. */
    pywebview?: { api: PineappleApi };
  }
}
