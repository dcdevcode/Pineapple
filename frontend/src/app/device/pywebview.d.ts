import type { DevicePresence, DeviceInfoResult } from './device.models';
import type { SyslogActionResult, SyslogReadResult } from '../syslog/syslog.models';
import type { BackupActionResult, BackupPreflight, BackupProgress } from '../backup/backup.models';
import type {
  AnalysisProgress,
  AppRow,
  CallRow,
  CaseSummary,
  ContactRow,
  DomainCount,
  FileRow,
  MessageRow,
  OpenCaseResult,
  Page,
  PathResult,
  PeekResult,
  QueryResult,
  StartResult,
} from '../analysis/analysis.models';

/** The Python `Api` object, exposed by pywebview as `window.pywebview.api`. */
export interface PineappleApi {
  connected_device(): Promise<DevicePresence>;
  get_device_info(udid: string): Promise<DeviceInfoResult>;
  start_syslog(): Promise<SyslogActionResult>;
  read_syslog(): Promise<SyslogReadResult>;
  stop_syslog(): Promise<{ ok: boolean }>;
  save_syslog(content: string): Promise<SyslogActionResult>;
  backup_preflight(): Promise<BackupPreflight>;
  choose_backup_path(deviceName: string): Promise<BackupActionResult>;
  start_backup(path: string, encrypt: boolean, password: string): Promise<BackupActionResult>;
  read_backup_progress(): Promise<BackupProgress>;
  cancel_backup(): Promise<{ ok: boolean }>;

  choose_pineapple_file(): Promise<PathResult>;
  choose_case_folder(): Promise<PathResult>;
  analysis_peek(pineapplePath: string): Promise<PeekResult>;
  start_analysis(
    pineapplePath: string,
    caseDir: string,
    title: string,
    password: string,
  ): Promise<StartResult>;
  read_analysis_progress(): Promise<AnalysisProgress>;
  cancel_analysis(): Promise<{ ok: boolean }>;
  open_case(caseDir: string): Promise<OpenCaseResult>;
  analysis_summary(): Promise<QueryResult<CaseSummary>>;
  analysis_apps(): Promise<QueryResult<AppRow[]>>;
  analysis_domains(): Promise<QueryResult<DomainCount[]>>;
  analysis_files(
    domain: string | null,
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<FileRow>>>;
  analysis_messages(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<MessageRow>>>;
  analysis_calls(limit: number, offset: number): Promise<QueryResult<Page<CallRow>>>;
  analysis_contacts(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<ContactRow>>>;
}

declare global {
  interface Window {
    /** Injected by pywebview only when running inside the desktop shell. */
    pywebview?: { api: PineappleApi };
  }
}
