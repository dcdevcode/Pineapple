import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { SyslogDialog } from './syslog-dialog';
import { SyslogService } from './syslog.service';
import type { SyslogLine } from './syslog.models';

function line(overrides: Partial<SyslogLine> = {}): SyslogLine {
  return {
    timestamp: '2026-08-29T12:00:00Z',
    process: 'SpringBoard',
    pid: 62,
    level: 'NOTICE',
    label: null,
    message: 'hello',
    ...overrides,
  };
}

function fakeService() {
  const lines = signal<SyslogLine[]>([]);
  return {
    lines,
    running: signal(true),
    paused: signal(false),
    error: signal<string | null>(null),
    dropped: signal(0),
    processes: signal<string[]>([]),
    start: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
    togglePause: vi.fn(),
    clear: vi.fn(),
    export: vi.fn().mockResolvedValue({ ok: true, path: '/tmp/syslog.txt' }),
  };
}

async function render(service: ReturnType<typeof fakeService>) {
  await TestBed.configureTestingModule({
    imports: [SyslogDialog],
    providers: [
      provideNoopAnimations(),
      { provide: SyslogService, useValue: service },
      { provide: MAT_DIALOG_DATA, useValue: { deviceName: 'Test iPhone' } },
      { provide: MatDialogRef, useValue: { close: vi.fn() } },
    ],
  }).compileComponents();
  const fixture = TestBed.createComponent(SyslogDialog);
  await fixture.whenStable();
  return fixture;
}

describe('SyslogDialog', () => {
  it('starts the stream on open and stops it on destroy', async () => {
    const service = fakeService();
    const fixture = await render(service);
    expect(service.start).toHaveBeenCalledOnce();

    fixture.destroy();
    expect(service.stop).toHaveBeenCalledOnce();
  });

  it('filters lines by text and by process', async () => {
    const service = fakeService();
    service.lines.set([
      line({ process: 'SpringBoard', message: 'boot complete' }),
      line({ process: 'wifid', message: 'scan started' }),
      line({ process: 'wifid', message: 'associated', label: 'com.apple.wifi/assoc' }),
    ]);
    const fixture = await render(service);
    const dialog = fixture.componentInstance;

    dialog.textFilter.set('scan');
    expect(dialog.filteredLines().map((l) => l.message)).toEqual(['scan started']);

    dialog.textFilter.set('');
    dialog.processFilter.set('wifid');
    expect(dialog.filteredLines()).toHaveLength(2);

    dialog.textFilter.set('assoc'); // also matches the label
    expect(dialog.filteredLines().map((l) => l.message)).toEqual(['associated']);
  });

  it('formats a timestamp and flags severe levels', async () => {
    const dialog = (await render(fakeService())).componentInstance;
    expect(dialog.formatTime('not a date')).toBe('not a date');
    expect(dialog.formatTime('2026-08-29T12:00:00Z')).not.toBe('2026-08-29T12:00:00Z');
    expect(dialog.isSevere('ERROR')).toBe(true);
    expect(dialog.isSevere('FAULT')).toBe(true);
    expect(dialog.isSevere('NOTICE')).toBe(false);
  });

  it('exports the filtered lines as Console-style text', async () => {
    const service = fakeService();
    service.lines.set([line({ message: 'keep' }), line({ process: 'other', message: 'drop' })]);
    const fixture = await render(service);
    fixture.componentInstance.textFilter.set('keep');

    await fixture.componentInstance.export();

    expect(service.export).toHaveBeenCalledWith(
      '2026-08-29T12:00:00Z SpringBoard[62] <NOTICE>: keep',
    );
  });
});
