import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatListModule } from '@angular/material/list';
import { MatRadioModule } from '@angular/material/radio';
import { ThemeService } from './theme.service';

type SectionId = 'theme';

interface Section {
  id: SectionId;
  label: string;
}

/**
 * Settings dialog: a left nav rail of sections and a content pane. For now the
 * only section is Theme (Light / Dark / System).
 */
@Component({
  selector: 'app-settings-dialog',
  imports: [FormsModule, MatListModule, MatRadioModule],
  templateUrl: './settings-dialog.html',
  styleUrl: './settings-dialog.scss',
})
export class SettingsDialog {
  readonly theme = inject(ThemeService);
  readonly preference = this.theme.preference;

  readonly sections: readonly Section[] = [{ id: 'theme', label: 'Theme' }];
  readonly activeSection = signal<SectionId>('theme');
}
