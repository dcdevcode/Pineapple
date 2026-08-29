/** A device as reported by the cheap usbmuxd-only presence check. */
export interface RawDevice {
  Udid: string;
  ConnectionType: string;
}

/** The lockdown values for a device, keyed by their lockdownd field name. */
export type DeviceInfo = Record<string, string | number | boolean | null>;

/** Result of `window.pywebview.api.get_device_info`. */
export interface DeviceInfoResult {
  ok: boolean;
  info?: DeviceInfo;
  error?: string;
}

/** What the Device tab is currently showing. */
export type DeviceState =
  | { status: 'idle' }
  | { status: 'connecting'; udid: string }
  | { status: 'unpaired'; udid: string; error: string }
  | { status: 'ready'; udid: string; name: string; info: DeviceInfo };
