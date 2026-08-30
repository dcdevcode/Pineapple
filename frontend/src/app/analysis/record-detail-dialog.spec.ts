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
});
