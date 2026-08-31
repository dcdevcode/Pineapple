import { Injectable, signal } from '@angular/core';
import type {
  AnalysisPhase,
  AnalysisProgress,
  AppRow,
  CallRow,
  CaseSummary,
  ContactRow,
  DomainCount,
  ExtractResult,
  FilePreview,
  FileRow,
  MessageRow,
  NoteRow,
  Page,
  PageQuery,
  PathResult,
  PeekResult,
  PhotoAlbumRow,
  PhotoRow,
  QueryResult,
  SafariBookmarkRow,
  SafariHistoryRow,
  StartResult,
  WhatsappChatRow,
  WhatsappMessageRow,
} from './analysis.models';
import type { PineappleApi } from '../device/pywebview';

const POLL_INTERVAL_MS = 500;

const IDLE: AnalysisProgress = {
  phase: 'idle',
  percent: 0,
  note: null,
  error: null,
  title: null,
  case_path: null,
  counts: {},
  skipped: [],
  running: false,
};

const NO_BRIDGE = 'The device bridge is not available.';

/**
 * Drives the Analysis tab over the pywebview bridge.
 *
 * Two concerns: running one `.pineapple` parse (`startAnalysis` → poll
 * `read_analysis_progress` into {@link progress}, opening the case on `done`),
 * and serving the open case's read queries. The open case is held by the Python
 * `Api` for the process lifetime; {@link summary} being non-null is what tells
 * the tab to show the browser. Without `window.pywebview` every method is an
 * idle no-op.
 */
@Injectable({ providedIn: 'root' })
export class AnalysisService {
  private readonly _progress = signal<AnalysisProgress>(IDLE);
  private readonly _summary = signal<CaseSummary | null>(null);
  readonly progress = this._progress.asReadonly();
  readonly summary = this._summary.asReadonly();

  private timer: ReturnType<typeof setInterval> | null = null;
  /** Bumped on every start; a poll from an earlier run bails out. */
  private generation = 0;

  async choosePineapple(): Promise<PathResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false };
    try {
      return await api.choose_pineapple_file();
    } catch {
      return { ok: false };
    }
  }

  async chooseCaseFolder(): Promise<PathResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false };
    try {
      return await api.choose_case_folder();
    } catch {
      return { ok: false };
    }
  }

  async peek(pineapplePath: string): Promise<PeekResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false, error: NO_BRIDGE };
    try {
      return await api.analysis_peek(pineapplePath);
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  async startAnalysis(
    pineapplePath: string,
    caseDir: string,
    title: string,
    password: string,
  ): Promise<StartResult> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false, error: NO_BRIDGE };

    this.stopPolling();
    const generation = ++this.generation;
    this._progress.set({ ...IDLE, phase: 'extracting', running: true });

    let started: StartResult;
    try {
      started = await api.start_analysis(pineapplePath, caseDir, title, password);
    } catch (error) {
      started = { ok: false, error: String(error) };
    }
    if (generation !== this.generation) return started;

    if (!started.ok) {
      this._progress.set({ ...IDLE, phase: 'error', error: started.error });
      return started;
    }

    this.timer = setInterval(() => void this.poll(generation), POLL_INTERVAL_MS);
    void this.poll(generation);
    return started;
  }

  async cancelAnalysis(): Promise<void> {
    try {
      await window.pywebview?.api.cancel_analysis();
    } catch {
      // Nothing actionable if the bridge is already gone.
    }
  }

  /** Run one poll cycle. Exposed so tests can await a single iteration. */
  async poll(generation = this.generation): Promise<void> {
    const api = window.pywebview?.api;
    if (!api || generation !== this.generation) return;

    let result: AnalysisProgress;
    try {
      result = await api.read_analysis_progress();
    } catch (error) {
      this._progress.update((current) => ({ ...current, error: String(error) }));
      return;
    }
    if (generation !== this.generation) return;

    this._progress.set(result);
    if (!result.running) {
      this.stopPolling();
      if (result.phase === 'done' && result.case_path) {
        await this.openCase(result.case_path);
      }
    }
  }

  async openCase(caseDir: string, password = ''): Promise<{ ok: boolean; error?: string }> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false, error: NO_BRIDGE };
    try {
      const result = await api.open_case(caseDir, password);
      if (!result.ok) return { ok: false, error: result.error };
      this._summary.set(result.summary);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  /** Supply the decryption key so an encrypted case can preview/extract files. */
  async unlock(password: string): Promise<{ ok: boolean; error?: string }> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false, error: NO_BRIDGE };
    try {
      const result = await api.analysis_unlock(password);
      if (!result.ok) return { ok: false, error: result.error };
      if (result.summary) this._summary.set(result.summary);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: String(error) };
    }
  }

  closeCase(): void {
    this._summary.set(null);
    this._progress.set(IDLE);
  }

  apps(): Promise<AppRow[]> {
    return this.query((api) => api.analysis_apps());
  }

  domains(): Promise<DomainCount[]> {
    return this.query((api) => api.analysis_domains());
  }

  files(q: PageQuery): Promise<Page<FileRow>> {
    return this.query((api) =>
      api.analysis_files(q.domain ?? null, q.search ?? null, q.limit, q.offset),
    );
  }

  messages(q: PageQuery): Promise<Page<MessageRow>> {
    return this.query((api) => api.analysis_messages(q.search ?? null, q.limit, q.offset));
  }

  calls(q: PageQuery): Promise<Page<CallRow>> {
    return this.query((api) => api.analysis_calls(q.limit, q.offset));
  }

  contacts(q: PageQuery): Promise<Page<ContactRow>> {
    return this.query((api) => api.analysis_contacts(q.search ?? null, q.limit, q.offset));
  }

  notes(q: PageQuery): Promise<Page<NoteRow>> {
    return this.query((api) => api.analysis_notes(q.search ?? null, q.limit, q.offset));
  }

  photos(q: PageQuery): Promise<Page<PhotoRow>> {
    return this.query((api) => api.analysis_photos(q.search ?? null, q.limit, q.offset));
  }

  photoAlbums(q: PageQuery): Promise<Page<PhotoAlbumRow>> {
    return this.query((api) => api.analysis_photo_albums(q.limit, q.offset));
  }

  safariHistory(q: PageQuery): Promise<Page<SafariHistoryRow>> {
    return this.query((api) => api.analysis_safari_history(q.search ?? null, q.limit, q.offset));
  }

  safariBookmarks(q: PageQuery): Promise<Page<SafariBookmarkRow>> {
    return this.query((api) => api.analysis_safari_bookmarks(q.search ?? null, q.limit, q.offset));
  }

  whatsappChats(q: PageQuery): Promise<Page<WhatsappChatRow>> {
    return this.query((api) => api.analysis_whatsapp_chats(q.limit, q.offset));
  }

  whatsappMessages(q: PageQuery): Promise<Page<WhatsappMessageRow>> {
    return this.query((api) =>
      api.analysis_whatsapp_messages(q.chatJid ?? null, q.search ?? null, q.limit, q.offset),
    );
  }

  /** A size-capped preview of one backup file, or `null` when the bridge is gone. */
  async previewFile(fileId: string): Promise<FilePreview | null> {
    const api = window.pywebview?.api;
    if (!api) return null;
    try {
      const envelope = await api.analysis_preview_file(fileId);
      return envelope.ok ? envelope.result : null;
    } catch {
      return null;
    }
  }

  /** Save one backup file to a user-chosen path (native dialog). */
  async extractFile(fileId: string): Promise<ExtractResult | { ok: false }> {
    const api = window.pywebview?.api;
    if (!api) return { ok: false };
    try {
      return await api.analysis_extract_file(fileId);
    } catch (error) {
      return { ok: false, error: String(error) } as ExtractResult;
    }
  }

  private stopPolling(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /** Unwrap a `{ ok, result }` query envelope, throwing on `{ ok: false }`. */
  private async query<T>(call: (api: PineappleApi) => Promise<QueryResult<T>>): Promise<T> {
    const api = window.pywebview?.api;
    if (!api) throw new Error(NO_BRIDGE);
    const envelope = await call(api);
    if (!envelope.ok) throw new Error(envelope.error);
    return envelope.result;
  }
}

/** Human label for a parse phase, for the progress view. */
export function phaseLabel(phase: AnalysisPhase): string {
  switch (phase) {
    case 'extracting':
      return 'Unpacking the archive…';
    case 'opening':
      return 'Opening the backup…';
    case 'indexing':
      return 'Indexing device info and files…';
    case 'parsing':
      return 'Parsing artifacts…';
    case 'writing_descriptor':
      return 'Writing the case…';
    case 'done':
      return 'Analysis complete';
    case 'error':
      return 'Analysis failed';
    case 'cancelled':
      return 'Analysis cancelled';
    default:
      return '';
  }
}
