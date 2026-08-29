import type { DevicePresence, DeviceInfoResult } from './device.models';
import type { SyslogActionResult, SyslogReadResult } from '../syslog/syslog.models';

/** The Python `Api` object, exposed by pywebview as `window.pywebview.api`. */
export interface PineappleApi {
  connected_device(): Promise<DevicePresence>;
  get_device_info(udid: string): Promise<DeviceInfoResult>;
  start_syslog(): Promise<SyslogActionResult>;
  read_syslog(): Promise<SyslogReadResult>;
  stop_syslog(): Promise<{ ok: boolean }>;
  save_syslog(content: string): Promise<SyslogActionResult>;
}

declare global {
  interface Window {
    /** Injected by pywebview only when running inside the desktop shell. */
    pywebview?: { api: PineappleApi };
  }
}
