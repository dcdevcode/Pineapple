/** One decoded syslog entry, as flattened by the backend `SyslogLine`. */
export interface SyslogLine {
  timestamp: string;
  process: string;
  pid: number;
  level: string;
  label: string | null;
  message: string;
}

/** Result of `window.pywebview.api.read_syslog`. */
export interface SyslogReadResult {
  lines: SyslogLine[];
  dropped: number;
  running: boolean;
  error: string | null;
}

/** Result of `start_syslog` / `save_syslog`. */
export interface SyslogActionResult {
  ok: boolean;
  error?: string;
  path?: string;
}
