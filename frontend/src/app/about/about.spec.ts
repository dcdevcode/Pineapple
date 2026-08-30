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
