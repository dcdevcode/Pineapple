import { Component, DestroyRef, inject } from '@angular/core';
import { MatTabsModule } from '@angular/material/tabs';
import { MatIconModule } from '@angular/material/icon';
import { Device } from './device/device';
import { Analysis } from './analysis/analysis';
import { About } from './about/about';
import { Brand } from './brand/brand';
import { DeviceService } from './device/device.service';

@Component({
  selector: 'app-root',
  imports: [MatTabsModule, MatIconModule, Device, Analysis, About, Brand],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly devices = inject(DeviceService);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    this.devices.start();
    this.destroyRef.onDestroy(() => this.devices.stop());
  }
}
