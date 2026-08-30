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

  it('should render the Device, Analysis and About tabs', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const labels = Array.from(fixture.nativeElement.querySelectorAll('.mdc-tab__text-label')).map(
      (el) => (el as HTMLElement).textContent?.trim(),
    );
    expect(labels).toEqual(['Device', 'Analysis', 'About']);
  });

  it('should start watching for devices on creation', () => {
    const start = vi.spyOn(DeviceService.prototype, 'start').mockImplementation(() => undefined);
    TestBed.createComponent(App);
    expect(start).toHaveBeenCalledOnce();
  });
});
