import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { SettingsDialog } from './settings-dialog';

/**
 * Floating settings entry point (bottom-right gear). Opens the settings dialog.
 */
@Component({
  selector: 'app-settings-button',
  imports: [MatButtonModule],
  templateUrl: './settings-button.html',
  styleUrl: './settings-button.scss',
})
export class SettingsButton {
  private readonly dialog = inject(MatDialog);

  openSettings(): void {
    this.dialog.open(SettingsDialog, {
      width: 'min(720px, 92vw)',
      height: 'min(460px, 85vh)',
      maxWidth: '92vw',
      autoFocus: false,
    });
  }
}
