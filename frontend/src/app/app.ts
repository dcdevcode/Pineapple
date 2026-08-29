import { Component } from '@angular/core';
import { MatTabsModule } from '@angular/material/tabs';
import { DeviceComponent } from './device/device';
import { AnalysisComponent } from './analysis/analysis';

@Component({
  selector: 'app-root',
  imports: [MatTabsModule, DeviceComponent, AnalysisComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
