import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { DeviceService } from './device/device.service';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
    }).compileComponents();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should render the Device, Analysis and About tabs, each with an icon', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const tabs = Array.from(fixture.nativeElement.querySelectorAll('.mdc-tab__text-label'));
    const labels = tabs.map((el) =>
      (el as HTMLElement).querySelector('.app-tab__label')?.textContent?.trim(),
    );
    expect(labels).toEqual(['Device', 'Analysis', 'About']);
    const icons = tabs.map((el) =>
      (el as HTMLElement).querySelector('mat-icon')?.textContent?.trim(),
    );
    expect(icons).toEqual(['phone_iphone', 'manage_search', 'info']);
  });

  it('should show the brand lockup in the top-left', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const logo = fixture.nativeElement.querySelector('.app-shell__brand .brand__logo');
    expect(logo?.getAttribute('src')).toBe('logo.png');
    expect(logo?.getAttribute('alt')).toBe('Pineapple');
  });

  it('should start watching for devices on creation', () => {
    const start = vi.spyOn(DeviceService.prototype, 'start').mockImplementation(() => undefined);
    TestBed.createComponent(App);
    expect(start).toHaveBeenCalledOnce();
  });
});
