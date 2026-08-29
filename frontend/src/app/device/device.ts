import { Component } from '@angular/core';
import { PhoneOutline } from './phone-outline/phone-outline';

@Component({
  selector: 'app-device',
  imports: [PhoneOutline],
  templateUrl: './device.html',
  styleUrl: './device.scss',
})
export class Device {}
