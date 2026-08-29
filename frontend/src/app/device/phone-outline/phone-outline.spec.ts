import { TestBed } from '@angular/core/testing';
import { PhoneOutline } from './phone-outline';

describe('PhoneOutline', () => {
  it('renders the iPhone SVG', async () => {
    const fixture = TestBed.createComponent(PhoneOutline);
    await fixture.whenStable();
    const svg = fixture.nativeElement.querySelector('svg');
    expect(svg).toBeTruthy();
    expect(svg.getAttribute('viewBox')).toBe('0 0 160 320');
  });
});
