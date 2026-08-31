import type { DevicePresence, DeviceInfoResult } from './device.models';
import type { SyslogActionResult, SyslogReadResult } from '../syslog/syslog.models';
import type { BackupActionResult, BackupPreflight, BackupProgress } from '../backup/backup.models';
import type {
  AccountRow,
  AnalysisProgress,
  AppRow,
  CalendarEventRow,
  CallRow,
  CaseSummary,
  ContactRow,
  DeviceUsageRow,
  DomainCount,
  ExtractResult,
  FilePreview,
  FileRow,
  MessageRow,
  NoteRow,
  OpenCaseResult,
  Page,
  PathResult,
  PeekCaseResult,
  PeekResult,
  PhotoAlbumRow,
  PhotoRow,
  QueryResult,
  SafariBookmarkRow,
  SafariHistoryRow,
  StartResult,
  VoicemailRow,
  WhatsappChatRow,
  WhatsappMessageRow,
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
  analysis_peek_case(caseDir: string): Promise<PeekCaseResult>;
  start_analysis(
    pineapplePath: string,
    caseDir: string,
    title: string,
    password: string,
  ): Promise<StartResult>;
  read_analysis_progress(): Promise<AnalysisProgress>;
  cancel_analysis(): Promise<{ ok: boolean }>;
  open_case(caseDir: string, password?: string): Promise<OpenCaseResult>;
  analysis_unlock(
    password: string,
  ): Promise<{ ok: boolean; error?: string; summary?: CaseSummary }>;
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
  analysis_notes(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<NoteRow>>>;
  analysis_safari_history(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<SafariHistoryRow>>>;
  analysis_safari_bookmarks(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<SafariBookmarkRow>>>;
  analysis_whatsapp_chats(
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<WhatsappChatRow>>>;
  analysis_whatsapp_messages(
    chatJid: string | null,
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<WhatsappMessageRow>>>;
  analysis_photos(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<PhotoRow>>>;
  analysis_photo_albums(limit: number, offset: number): Promise<QueryResult<Page<PhotoAlbumRow>>>;
  analysis_calendar(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<CalendarEventRow>>>;
  analysis_voicemail(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<VoicemailRow>>>;
  analysis_device_usage(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<DeviceUsageRow>>>;
  analysis_accounts(
    search: string | null,
    limit: number,
    offset: number,
  ): Promise<QueryResult<Page<AccountRow>>>;
  analysis_preview_file(fileId: string): Promise<QueryResult<FilePreview>>;
  analysis_extract_file(fileId: string): Promise<ExtractResult | { ok: false }>;
}

declare global {
  interface Window {
    /** Injected by pywebview only when running inside the desktop shell. */
    pywebview?: { api: PineappleApi };
  }
}
