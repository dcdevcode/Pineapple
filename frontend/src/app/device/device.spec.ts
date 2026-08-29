import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Device } from './device';
import { DeviceService } from './device.service';
import type { DeviceInfo, DeviceState } from './device.models';

const SAMPLE_INFO: DeviceInfo = {
  DeviceName: 'Diego’s iPhone',
  ProductType: 'iPhone15,2',
  ProductVersion: '18.5',
  TotalDiskCapacity: 128_000_000_000,
  PasswordProtected: true,
};

describe('Device', () => {
  const state = signal<DeviceState>({ status: 'idle' });

  beforeEach(async () => {
    state.set({ status: 'idle' });
    await TestBed.configureTestingModule({
      imports: [Device],
      providers: [{ provide: DeviceService, useValue: { state } }],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(Device);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('shows the empty hint and no button when idle', async () => {
    const el = await render();
    expect(el.querySelector('.device__hint')?.textContent?.trim()).toBe(
      'Connect a device to get started',
    );
    expect(el.querySelector('app-phone-outline')).toBeTruthy();
    expect(el.querySelector('button')).toBeNull();
  });

  it('shows a disabled button while connecting', async () => {
    state.set({ status: 'connecting', udid: 'A' });
    const el = await render();
    expect(el.querySelector('.device__status')?.textContent).toContain(
      'Reading device information',
    );
    expect(el.querySelector('button')?.disabled).toBe(true);
  });

  it('shows the trust hint and error while unpaired', async () => {
    state.set({ status: 'unpaired', udid: 'A', error: 'Not trusted' });
    const el = await render();
    expect(el.querySelector('.device__status')?.textContent).toContain('tap');
    expect(el.querySelector('.device__detail')?.textContent).toContain('Not trusted');
    expect(el.querySelector('button')?.disabled).toBe(true);
  });

  it('renders the name, formatted info and an enabled button when ready', async () => {
    state.set({ status: 'ready', udid: 'A', name: 'Diego’s iPhone', info: SAMPLE_INFO });
    const el = await render();

    expect(el.querySelector('.device__name')?.textContent?.trim()).toBe('Diego’s iPhone');

    const rows = Array.from(el.querySelectorAll('.device__row')).map((row) => ({
      label: row.querySelector('dt')?.textContent?.trim(),
      value: row.querySelector('dd')?.textContent?.trim(),
    }));
    expect(rows).toContainEqual({ label: 'iOS Version', value: '18.5' });
    expect(rows).toContainEqual({ label: 'Capacity', value: '128 GB' });
    expect(rows).toContainEqual({ label: 'Passcode Set', value: 'Yes' });

    const button = el.querySelector('button')!;
    expect(button.textContent?.trim()).toBe('Create Pineapple Logical Image');
    expect(button.disabled).toBe(false);
  });

  it('skips rows for missing fields', async () => {
    state.set({
      status: 'ready',
      udid: 'A',
      name: 'x',
      info: { DeviceName: 'x', ProductType: 'iPhone15,2' },
    });
    const el = await render();
    const labels = Array.from(el.querySelectorAll('.device__row dt')).map((dt) =>
      dt.textContent?.trim(),
    );
    expect(labels).toContain('Model');
    expect(labels).not.toContain('Serial Number');
  });
});
