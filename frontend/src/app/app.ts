import { Component } from '@angular/core';
import { MatTabsModule } from '@angular/material/tabs';
import { Device } from './device/device';
import { Analysis } from './analysis/analysis';

@Component({
  selector: 'app-root',
  imports: [MatTabsModule, Device, Analysis],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
