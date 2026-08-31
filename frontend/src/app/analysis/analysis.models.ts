/** Types mirroring the `analysis_*` bridge on the Python `Api`. */

/** Phases the backend `AnalysisRun` moves through, from `runner.py`. */
export type AnalysisPhase =
  | 'idle'
  | 'extracting'
  | 'opening'
  | 'indexing'
  | 'parsing'
  | 'writing_descriptor'
  | 'done'
  | 'error'
  | 'cancelled';

/** Phases where the parse is still working and the dialog must stay open. */
export const RUNNING_PHASES: readonly AnalysisPhase[] = [
  'extracting',
  'opening',
  'indexing',
  'parsing',
  'writing_descriptor',
];

/** Snapshot from `read_analysis_progress`. */
export interface AnalysisProgress {
  phase: AnalysisPhase;
  percent: number;
  note: string | null;
  error: string | null;
  title: string | null;
  case_path: string | null;
  counts: Record<string, number>;
  skipped: string[];
  running: boolean;
}

/** Device facts — `peek` uses `name`, a parsed `backup_info` row uses
 *  `device_name`; the Overview view reads whichever is present. */
export interface DeviceFacts {
  name?: string | null;
  device_name?: string | null;
  product_type?: string | null;
  product_name?: string | null;
  product_version?: string | null;
  build_version?: string | null;
  serial?: string | null;
  udid?: string | null;
  last_backup_date?: string | null;
  is_encrypted?: boolean | number | null;
  was_passcode_set?: boolean | number | null;
}

export interface CaseSource {
  path?: string;
  sha256?: string;
  is_encrypted?: boolean;
}

export interface ParseReport {
  status?: string;
  finished_at?: string;
  counts?: Record<string, number>;
  skipped?: string[];
}

export interface CaseDescriptor {
  title: string;
  created_at: string;
  tool_version: string;
  schema_version: number;
  source: CaseSource;
  device: DeviceFacts;
  parse: ParseReport;
}

export interface CaseSummary {
  title: string;
  device: DeviceFacts;
  source: CaseSource;
  parse: ParseReport;
  counts: Record<string, number>;
  is_encrypted: boolean;
  files_unlocked: boolean;
}

/** One page of a paged `analysis_*` query. */
export interface Page<T> {
  rows: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AppRow {
  bundle_id: string;
  name: string | null;
  version: string | null;
}

export interface FileRow {
  file_id: string;
  domain: string;
  relative_path: string;
  is_dir: number;
  size: number;
  mtime: string | null;
  btime: string | null;
  target: string | null;
}

export interface MessageRow {
  rowid: number;
  chat_id: number | null;
  address: string | null;
  service: string | null;
  is_from_me: number;
  date_utc: string | null;
  text: string | null;
  attachments: number;
}

export interface CallRow {
  rowid: number;
  address: string | null;
  service: string | null;
  direction: string | null;
  date_utc: string | null;
  duration_seconds: number;
}

export interface ContactRow {
  rowid: number;
  first: string | null;
  last: string | null;
  organization: string | null;
  phones: string | null;
  emails: string | null;
}

export interface NoteRow {
  rowid: number;
  folder: string | null;
  title: string | null;
  snippet: string | null;
  body: string | null;
  created_utc: string | null;
  modified_utc: string | null;
}

export interface SafariHistoryRow {
  rowid: number;
  url: string | null;
  title: string | null;
  visit_utc: string | null;
  visit_count: number;
}

export interface SafariBookmarkRow {
  rowid: number;
  title: string | null;
  url: string | null;
  folder: string | null;
}

export interface WhatsappChatRow {
  rowid: number;
  jid: string | null;
  name: string | null;
  last_message_utc: string | null;
  message_count: number;
}

export interface WhatsappMessageRow {
  rowid: number;
  chat_jid: string | null;
  chat_name: string | null;
  from_me: number;
  sender: string | null;
  date_utc: string | null;
  text: string | null;
  media_type: string | null;
}

export interface PhotoRow {
  rowid: number;
  file_id: string | null;
  filename: string | null;
  directory: string | null;
  kind: string | null;
  created_utc: string | null;
  added_utc: string | null;
  width: number | null;
  height: number | null;
  favorite: number;
  hidden: number;
  trashed: number;
  latitude: number | null;
  longitude: number | null;
}

export interface PhotoAlbumRow {
  rowid: number;
  title: string | null;
  kind: string | null;
  count: number;
  start_utc: string | null;
  end_utc: string | null;
}

export interface CalendarEventRow {
  rowid: number;
  calendar: string | null;
  title: string | null;
  location: string | null;
  notes: string | null;
  start_utc: string | null;
  end_utc: string | null;
  all_day: number;
  invitees: string | null;
}

export interface VoicemailRow {
  rowid: number;
  sender: string | null;
  received_utc: string | null;
  duration_seconds: number;
  trashed: number;
  transcript: string | null;
}

export interface DeviceUsageRow {
  rowid: number;
  stream: string | null;
  bundle_id: string | null;
  value: string | null;
  start_utc: string | null;
  end_utc: string | null;
  duration_seconds: number;
}

export interface AccountRow {
  rowid: number;
  type: string | null;
  identifier: string | null;
  description: string | null;
  username: string | null;
  added_utc: string | null;
  credential_type: string | null;
}

export interface DomainCount {
  domain: string;
  count: number;
}

/** Result of `analysis_preview_file` — a size-capped view of one backup file. */
export type FilePreview =
  | { kind: 'text'; name: string; size: number; text: string; truncated: boolean }
  | { kind: 'plist'; name: string; size: number; json: unknown }
  | {
      kind: 'image';
      name: string;
      size: number;
      mime: string;
      data_base64: string;
      truncated: boolean;
    }
  | { kind: 'binary'; name: string; size: number; truncated: boolean }
  | { kind: 'unavailable'; name: string; reason: string; target?: string };

/** Result of `analysis_extract_file`. */
export type ExtractResult = { ok: true; path: string } | { ok: false; error?: string };

/** Result of `choose_pineapple_file` / `choose_case_folder`. */
export type PathResult = { ok: true; path: string } | { ok: false };

/** Result of `analysis_peek`. */
export type PeekResult =
  | { ok: true; encrypted: boolean; device: DeviceFacts; default_title: string }
  | { ok: false; error: string };

/** Result of `analysis_peek_case` — is an existing case folder encrypted? */
export type PeekCaseResult =
  { ok: true; encrypted: boolean; title: string } | { ok: false; error: string };

/** Result of `start_analysis`. */
export type StartResult = { ok: true } | { ok: false; error: string };

/** Result of `open_case`. */
export type OpenCaseResult =
  { ok: true; descriptor: CaseDescriptor; summary: CaseSummary } | { ok: false; error: string };

/** Result of every `analysis_*` read query. */
export type QueryResult<T> = { ok: true; result: T } | { ok: false; error: string };

/** Paging + optional search shared by the artifact queries. */
export interface PageQuery {
  limit: number;
  offset: number;
  search?: string;
  domain?: string;
  chatJid?: string;
}
