import { TestBed } from '@angular/core/testing';
import { About } from './about';

describe('About', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [About] }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(About);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the brand lockup and the author', async () => {
    const el = await render();
    expect(el.querySelector('.about__brand img')?.getAttribute('alt')).toBe('Pineapple');
    expect(el.querySelector('.about__byline')?.textContent).toContain('Diego Corona');
  });

  it('shows the Spider-Man creed with its film attribution', async () => {
    const el = await render();
    const creed = el.querySelector('.about__creed');
    expect(creed?.textContent).toContain('With great power comes great responsibility');
    expect(creed?.querySelector('cite')?.textContent).toContain('Spider-Man (2002)');
  });

  it('states the project is open source under the MIT License', async () => {
    const el = await render();
    const license = el.querySelector('.about__license')?.textContent ?? '';
    expect(license).toContain('open source');
    expect(license).toContain('MIT License');
  });

  it('shows the legal notice with its key points', async () => {
    const el = await render();
    const legal = el.querySelector('.about__legal')?.textContent ?? '';
    expect(el.querySelectorAll('.about__legal-list li')).toHaveLength(4);
    expect(legal).toContain('authorized forensic examination');
    expect(legal).toContain('without warranty of any kind');
    expect(legal).toContain('Apple Inc.');
  });

  it('credits the four core projects, each as an outbound link', async () => {
    const el = await render();
    const links = Array.from(el.querySelectorAll<HTMLAnchorElement>('.about__credit-name a'));
    expect(links.map((a) => a.textContent?.trim())).toEqual([
      'pymobiledevice3',
      'iphone_backup_decrypt',
      'python-typedstream',
      'pywebview',
    ]);
    for (const link of links) {
      expect(link.getAttribute('href')).toMatch(/^https:\/\//);
      expect(link.getAttribute('target')).toBe('_blank');
      expect(link.getAttribute('rel')).toContain('noopener');
    }
  });
});
