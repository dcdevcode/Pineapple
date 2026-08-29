import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { DeviceService } from './device.service';
import type { DeviceInfo } from './device.models';
import { PhoneOutline } from './phone-outline/phone-outline';

type FieldValue = string | number | boolean;

interface InfoField {
  key: string;
  label: string;
  format?: (value: FieldValue) => string;
}

/** Decimal GB, matching how iOS reports capacity under Settings > About. */
function formatBytes(value: FieldValue): string {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return String(value);
  return `${Math.round(bytes / 1000 ** 3)} GB`;
}

function formatBool(value: FieldValue): string {
  return value ? 'Yes' : 'No';
}

@Component({
  selector: 'app-device',
  imports: [MatButtonModule, PhoneOutline],
  templateUrl: './device.html',
  styleUrl: './device.scss',
})
export class Device {
  private readonly devices = inject(DeviceService);
  readonly state = this.devices.state;

  /** Rows shown in the info panel (DeviceName is the heading, not a row). */
  readonly fields: readonly InfoField[] = [
    { key: 'DeviceClass', label: 'Device Class' },
    { key: 'ProductType', label: 'Model' },
    { key: 'ProductName', label: 'Product Name' },
    { key: 'ModelNumber', label: 'Model Number' },
    { key: 'HardwareModel', label: 'Hardware Model' },
    { key: 'ProductVersion', label: 'iOS Version' },
    { key: 'BuildVersion', label: 'Build' },
    { key: 'SerialNumber', label: 'Serial Number' },
    { key: 'UniqueDeviceID', label: 'UDID' },
    { key: 'TotalDiskCapacity', label: 'Capacity', format: formatBytes },
    { key: 'RegionInfo', label: 'Region' },
    { key: 'CPUArchitecture', label: 'CPU Architecture' },
    { key: 'WiFiAddress', label: 'Wi-Fi Address' },
    { key: 'BluetoothAddress', label: 'Bluetooth Address' },
    { key: 'TimeZone', label: 'Time Zone' },
    { key: 'PasswordProtected', label: 'Passcode Set', format: formatBool },
  ];

  /** Formatted value for a field, or null when it is missing / empty. */
  displayValue(info: DeviceInfo, field: InfoField): string | null {
    const raw = info[field.key];
    if (raw === null || raw === undefined || raw === '') return null;
    return field.format ? field.format(raw) : String(raw);
  }
}
