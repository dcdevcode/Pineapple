import { TestBed } from '@angular/core/testing';
import { Overview } from './overview';
import type { CaseSummary } from '../analysis.models';

const SUMMARY: CaseSummary = {
  title: 'F17ABC',
  device: {
    device_name: 'Test iPhone',
    product_name: 'iPhone 13',
    product_version: '17.5.1',
    serial: 'F17ABC',
    is_encrypted: 1,
  },
  source: { path: '/x.pineapple', sha256: 'deadbeef', is_encrypted: true },
  parse: { status: 'done', counts: { messages: 3 }, skipped: ['calls: not present in the backup'] },
  counts: { apps: 1, files: 5, messages: 3, calls: 0, contacts: 2 },
  is_encrypted: true,
  files_unlocked: false,
};

describe('Overview', () => {
  async function render(summary: CaseSummary) {
    await TestBed.configureTestingModule({ imports: [Overview] }).compileComponents();
    const fixture = TestBed.createComponent(Overview);
    fixture.componentRef.setInput('summary', summary);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('lists device facts, counts, skipped notes and source', async () => {
    const el = await render(SUMMARY);
    expect(el.textContent).toContain('iPhone 13');
    expect(el.textContent).toContain('17.5.1');
    expect(el.textContent).toContain('deadbeef');
    expect(el.textContent).toContain('calls: not present in the backup');

    const rows = Array.from(el.querySelectorAll('.overview__row')).map((r) => ({
      label: r.querySelector('dt')?.textContent?.trim(),
      value: r.querySelector('dd')?.textContent?.trim(),
    }));
    expect(rows).toContainEqual({ label: 'Messages', value: '3' });
    expect(rows).toContainEqual({ label: 'Encrypted Backup', value: 'Yes' });
  });

  it('omits missing device fields', async () => {
    const el = await render({ ...SUMMARY, device: { serial: 'S' } });
    const labels = Array.from(el.querySelectorAll('.overview__row dt')).map((dt) =>
      dt.textContent?.trim(),
    );
    expect(labels).toContain('Serial Number');
    expect(labels).not.toContain('Model');
  });
});
