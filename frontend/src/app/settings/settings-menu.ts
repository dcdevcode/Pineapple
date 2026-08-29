import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { ThemeService, type ThemePreference } from './theme.service';

interface ThemeOption {
  value: ThemePreference;
  label: string;
}

/**
 * Floating settings entry point (bottom-right gear). Opens a menu whose first
 * setting switches the theme between Light / Dark / System.
 */
@Component({
  selector: 'app-settings-menu',
  imports: [MatButtonModule, MatMenuModule],
  templateUrl: './settings-menu.html',
  styleUrl: './settings-menu.scss',
})
export class SettingsMenu {
  readonly theme = inject(ThemeService);
  readonly preference = this.theme.preference;

  readonly themeOptions: readonly ThemeOption[] = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
    { value: 'system', label: 'System' },
  ];
}
