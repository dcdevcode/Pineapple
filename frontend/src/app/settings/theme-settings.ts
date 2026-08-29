import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatRadioModule } from '@angular/material/radio';
import { ThemeService, type ThemePreference } from './theme.service';

/** Theme section of the settings dialog: Light / Dark / System. */
@Component({
  selector: 'app-theme-settings',
  imports: [FormsModule, MatRadioModule],
  templateUrl: './theme-settings.html',
  styleUrl: './theme-settings.scss',
})
export class ThemeSettings {
  private readonly theme = inject(ThemeService);
  readonly preference = this.theme.preference;

  select(preference: ThemePreference): void {
    this.theme.setPreference(preference);
  }
}
