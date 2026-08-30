import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { RecordDetailDialog, type RecordDetailData } from './record-detail-dialog';

async function render(data: RecordDetailData) {
  await TestBed.configureTestingModule({
    imports: [RecordDetailDialog],
    providers: [provideNoopAnimations(), { provide: MAT_DIALOG_DATA, useValue: data }],
  }).compileComponents();
  const fixture = TestBed.createComponent(RecordDetailDialog);
  await fixture.whenStable();
  return fixture;
}

describe('RecordDetailDialog', () => {
  it('renders fields, long values in a block, and copies to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });

    const fixture = await render({
      title: 'Ada',
      fields: [
        { label: 'Phone', value: '+15551234567' },
        { label: 'Message', value: 'a very long body', long: true },
      ],
    });
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('Ada');
    expect(el.querySelector('.detail__block')?.textContent).toContain('a very long body');

    const copy = el.querySelector<HTMLButtonElement>('.detail__copy')!;
    expect(copy.getAttribute('aria-label')).toBe('Copy Phone');
    copy.click();
    expect(writeText).toHaveBeenCalledWith('+15551234567');
    vi.unstubAllGlobals();
  });

  it('shows an image preview and runs the extract action', async () => {
    const extract = vi.fn().mockResolvedValue({ ok: true, path: '/tmp/out.png' });
    const fixture = await render({
      title: 'photo.png',
      fields: [],
      preview: {
        kind: 'image',
        name: 'photo.png',
        size: 10,
        mime: 'image/png',
        data_base64: 'AAA',
        truncated: false,
      },
      extract,
    });
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('img.detail__image')?.getAttribute('src')).toBe(
      'data:image/png;base64,AAA',
    );

    const button = Array.from(el.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Extract'),
    )!;
    button.click();
    await fixture.whenStable();
    expect(extract).toHaveBeenCalled();
    expect(el.textContent).toContain('/tmp/out.png');
  });

  it('has no Extract button without an extract action', async () => {
    const fixture = await render({ title: 'x', fields: [] });
    const el = fixture.nativeElement as HTMLElement;
    expect(
      Array.from(el.querySelectorAll('button')).some((b) => b.textContent?.includes('Extract')),
    ).toBe(false);
  });

  it('renders a text preview and notes when it is truncated', async () => {
    const fixture = await render({
      title: 'notes.txt',
      fields: [],
      preview: { kind: 'text', name: 'notes.txt', size: 99, text: 'first line', truncated: true },
    });
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.detail__block--preview')?.textContent).toContain('first line');
    expect(el.textContent).toContain('Preview truncated');
  });

  it('pretty-prints a plist preview as JSON', async () => {
    const fixture = await render({
      title: 'Info.plist',
      fields: [],
      preview: { kind: 'plist', name: 'Info.plist', size: 20, json: { a: 1, b: ['x'] } },
    });
    const block = (fixture.nativeElement as HTMLElement).querySelector('.detail__block--preview');
    expect(block?.textContent).toContain('"a": 1');
    expect(block?.textContent).toContain('"b"');
  });

  it('explains a binary preview', async () => {
    const fixture = await render({
      title: 'blob',
      fields: [],
      preview: { kind: 'binary', name: 'blob', size: 4096, truncated: false },
    });
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Binary file (4096 bytes)',
    );
  });

  it('shows the symlink target for an unavailable symlink preview', async () => {
    const fixture = await render({
      title: 'link',
      fields: [],
      preview: { kind: 'unavailable', name: 'link', reason: 'symlink', target: 'SMS/sms.db' },
    });
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('SMS/sms.db');
  });

  it('explains an unavailable directory preview', async () => {
    const fixture = await render({
      title: 'SMS',
      fields: [],
      preview: { kind: 'unavailable', name: 'SMS', reason: 'directory' },
    });
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('This is a folder');
  });
});
