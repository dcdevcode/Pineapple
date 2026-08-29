import type { RawDevice, DeviceInfoResult } from './device.models';

/** The Python `Api` object, exposed by pywebview as `window.pywebview.api`. */
export interface PineappleApi {
  list_devices(): Promise<RawDevice[]>;
  get_device_info(udid: string): Promise<DeviceInfoResult>;
}

declare global {
  interface Window {
    /** Injected by pywebview only when running inside the desktop shell. */
    pywebview?: { api: PineappleApi };
  }
}
