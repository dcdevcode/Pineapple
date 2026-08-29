import { Component, DestroyRef, inject } from '@angular/core';
import { MatTabsModule } from '@angular/material/tabs';
import { Device } from './device/device';
import { Analysis } from './analysis/analysis';
import { DeviceService } from './device/device.service';

@Component({
  selector: 'app-root',
  imports: [MatTabsModule, Device, Analysis],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly devices = inject(DeviceService);

  constructor() {
    this.devices.start();
    inject(DestroyRef).onDestroy(() => this.devices.stop());
  }
}
