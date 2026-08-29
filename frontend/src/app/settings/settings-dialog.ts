import { Component, signal } from '@angular/core';
import { MatListModule } from '@angular/material/list';
import { ThemeSettings } from './theme-settings';

type SectionId = 'theme';

interface Section {
  id: SectionId;
  label: string;
}

/**
 * Settings dialog shell: a left nav rail of sections and a content pane. Each
 * section is its own component; for now the only one is Theme.
 */
@Component({
  selector: 'app-settings-dialog',
  imports: [MatListModule, ThemeSettings],
  templateUrl: './settings-dialog.html',
  styleUrl: './settings-dialog.scss',
})
export class SettingsDialog {
  readonly sections: readonly Section[] = [{ id: 'theme', label: 'Theme' }];
  readonly activeSection = signal<SectionId>('theme');
}
