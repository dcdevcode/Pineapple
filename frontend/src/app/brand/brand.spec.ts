import { TestBed } from '@angular/core/testing';
import { Brand } from './brand';

describe('Brand', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [Brand] }).compileComponents();
  });

  async function render(size?: 'compact' | 'large') {
    const fixture = TestBed.createComponent(Brand);
    if (size) fixture.componentRef.setInput('size', size);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders the logo lockup', async () => {
    const img = (await render()).querySelector<HTMLImageElement>('.brand__logo');
    expect(img?.getAttribute('src')).toBe('logo.png');
    expect(img?.getAttribute('alt')).toBe('Pineapple');
  });

  it('defaults to compact and switches to the large modifier', async () => {
    expect((await render()).classList.contains('brand--large')).toBe(false);
    expect((await render('large')).classList.contains('brand--large')).toBe(true);
  });
});
