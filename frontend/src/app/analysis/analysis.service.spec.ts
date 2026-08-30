import { TestBed } from '@angular/core/testing';
import { AnalysisService, phaseLabel } from './analysis.service';
import type { AnalysisProgress } from './analysis.models';
import type { PineappleApi } from '../device/pywebview';

function useBridge(api: Partial<PineappleApi>): void {
  window.pywebview = { api: api as PineappleApi };
}

const POLL_WINDOW = 700;

function progress(overrides: Partial<AnalysisProgress> = {}): AnalysisProgress {
  return {
    phase: 'parsing',
    percent: 50,
    note: null,
    error: null,
    title: 'F17ABC',
    case_path: '/cases/x',
    counts: {},
    skipped: [],
    running: true,
    ...overrides,
  };
}

const SUMMARY = {
  title: 'F17ABC',
  device: { serial: 'F17ABC' },
  source: {},
  parse: {},
  counts: { messages: 3 },
};

function makeApi() {
  return {
    choose_pineapple_file: vi.fn().mockResolvedValue({ ok: true, path: '/x.pineapple' }),
    choose_case_folder: vi.fn().mockResolvedValue({ ok: true, path: '/cases/x' }),
    analysis_peek: vi
      .fn()
      .mockResolvedValue({ ok: true, encrypted: false, device: {}, default_title: 'F17ABC' }),
    start_analysis: vi.fn().mockResolvedValue({ ok: true }),
    read_analysis_progress: vi.fn().mockResolvedValue(progress()),
    cancel_analysis: vi.fn().mockResolvedValue({ ok: true }),
    open_case: vi.fn().mockResolvedValue({ ok: true, descriptor: {}, summary: SUMMARY }),
    analysis_apps: vi.fn().mockResolvedValue({ ok: true, result: [{ bundle_id: 'com.a' }] }),
    analysis_files: vi
      .fn()
      .mockResolvedValue({ ok: true, result: { rows: [], total: 0, limit: 50, offset: 0 } }),
  };
}

describe('AnalysisService', () => {
  let service: AnalysisService;

  beforeEach(() => {
    service = TestBed.inject(AnalysisService);
  });

  afterEach(() => {
    delete window.pywebview;
    vi.useRealTimers();
  });

  it('is an idle no-op without the bridge', async () => {
    expect(await service.choosePineapple()).toEqual({ ok: false });
    expect(await service.peek('/x')).toEqual({
      ok: false,
      error: 'The device bridge is not available.',
    });
    expect(await service.startAnalysis('/x', '/c', 't', '')).toEqual({
      ok: false,
      error: 'The device bridge is not available.',
    });
    await expect(service.apps()).rejects.toThrow();
    expect(service.summary()).toBeNull();
  });

  it('passes the peek result through', async () => {
    const api = makeApi();
    api.analysis_peek.mockResolvedValue({
      ok: true,
      encrypted: true,
      device: { serial: 'S' },
      default_title: 'S',
    });
    useBridge(api);

    expect(await service.peek('/x.pineapple')).toEqual({
      ok: true,
      encrypted: true,
      device: { serial: 'S' },
      default_title: 'S',
    });
  });

  it('starts a parse and polls progress into the signal', async () => {
    const api = makeApi();
    api.read_analysis_progress.mockResolvedValue(progress({ percent: 70 }));
    useBridge(api);

    await service.startAnalysis('/x.pineapple', '/cases/x', 'My case', 'pw');

    expect(api.start_analysis).toHaveBeenCalledWith('/x.pineapple', '/cases/x', 'My case', 'pw');
    expect(service.progress().phase).toBe('parsing');
    expect(service.progress().percent).toBe(70);
  });

  it('stops polling and opens the case when the parse is done', async () => {
    vi.useFakeTimers();
    const api = makeApi();
    api.read_analysis_progress.mockResolvedValue(
      progress({ phase: 'done', running: false, percent: 100 }),
    );
    useBridge(api);

    await service.startAnalysis('/x.pineapple', '/cases/x', 't', '');
    await vi.advanceTimersByTimeAsync(POLL_WINDOW);
    const calls = api.read_analysis_progress.mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL_WINDOW * 3);

    expect(api.read_analysis_progress.mock.calls.length).toBe(calls);
    expect(api.open_case).toHaveBeenCalledWith('/cases/x', '');
    expect(service.summary()).toEqual(SUMMARY);
  });

  it('surfaces a refused start', async () => {
    const api = makeApi();
    api.start_analysis.mockResolvedValue({ ok: false, error: 'already holds an analysis' });
    useBridge(api);

    const result = await service.startAnalysis('/x', '/c', 't', '');

    expect(result).toEqual({ ok: false, error: 'already holds an analysis' });
    expect(service.progress().phase).toBe('error');
  });

  it('openCase sets the summary; closeCase clears it', async () => {
    const api = makeApi();
    useBridge(api);

    expect(await service.openCase('/cases/x')).toEqual({ ok: true });
    expect(service.summary()).toEqual(SUMMARY);

    service.closeCase();
    expect(service.summary()).toBeNull();
  });

  it('unwraps a query envelope and throws on failure', async () => {
    const api = makeApi();
    api.analysis_files.mockResolvedValue({ ok: false, error: 'No analysis is open.' });
    useBridge(api);

    expect(await service.apps()).toEqual([{ bundle_id: 'com.a' }]);
    await expect(service.files({ limit: 50, offset: 0 })).rejects.toThrow('No analysis is open.');
  });

  it('unwraps the new artifact query wrappers', async () => {
    const page = { rows: [{ rowid: 1 }], total: 1, limit: 50, offset: 0 };
    const api = {
      ...makeApi(),
      analysis_notes: vi.fn().mockResolvedValue({ ok: true, result: page }),
      analysis_safari_history: vi.fn().mockResolvedValue({ ok: true, result: page }),
      analysis_safari_bookmarks: vi.fn().mockResolvedValue({ ok: true, result: page }),
      analysis_whatsapp_chats: vi.fn().mockResolvedValue({ ok: true, result: page }),
      analysis_whatsapp_messages: vi.fn().mockResolvedValue({ ok: true, result: page }),
    };
    useBridge(api);

    expect(await service.notes({ limit: 50, offset: 0 })).toEqual(page);
    expect(await service.safariHistory({ limit: 50, offset: 0 })).toEqual(page);
    expect(await service.safariBookmarks({ limit: 50, offset: 0 })).toEqual(page);
    expect(await service.whatsappChats({ limit: 50, offset: 0 })).toEqual(page);
    await service.whatsappMessages({ limit: 50, offset: 0, chatJid: 'a@x' });
    expect(api.analysis_whatsapp_messages).toHaveBeenCalledWith('a@x', null, 50, 0);
  });

  it('previewFile / extractFile / unlock go through the bridge', async () => {
    const api = {
      ...makeApi(),
      analysis_preview_file: vi.fn().mockResolvedValue({
        ok: true,
        result: { kind: 'text', name: 'a', size: 1, text: 'x', truncated: false },
      }),
      analysis_extract_file: vi.fn().mockResolvedValue({ ok: true, path: '/tmp/a' }),
      analysis_unlock: vi.fn().mockResolvedValue({ ok: true, summary: SUMMARY }),
    };
    useBridge(api);

    expect((await service.previewFile('id'))?.kind).toBe('text');
    expect(await service.extractFile('id')).toEqual({ ok: true, path: '/tmp/a' });
    expect(await service.unlock('pw')).toEqual({ ok: true });
    expect(service.summary()).toEqual(SUMMARY);
  });

  it('labels phases', () => {
    expect(phaseLabel('parsing')).toContain('Parsing');
    expect(phaseLabel('done')).toContain('complete');
    expect(phaseLabel('idle')).toBe('');
  });
});
