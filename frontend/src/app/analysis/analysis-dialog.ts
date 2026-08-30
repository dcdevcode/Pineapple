import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { AnalysisService, phaseLabel } from './analysis.service';
import { RUNNING_PHASES, type AnalysisPhase, type DeviceFacts } from './analysis.models';

type Step = 'pick' | 'configure' | 'progress' | 'result';

const TERMINAL_PHASES: readonly AnalysisPhase[] = ['done', 'error', 'cancelled'];

/**
 * Guides one `.pineapple` parse: pick the image, confirm the device and name
 * the analysis, pick a case folder, then watch progress. While the parse runs
 * the dialog cannot be closed — only the Cancel button stops it. On `done` the
 * tab already shows the case (the service opened it), so this just reports.
 */
@Component({
  selector: 'app-analysis-dialog',
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatProgressBarModule],
  templateUrl: './analysis-dialog.html',
  styleUrl: './analysis-dialog.scss',
})
export class AnalysisDialog {
  private readonly analysis = inject(AnalysisService);
  private readonly dialogRef = inject(MatDialogRef<AnalysisDialog>);

  readonly progress = this.analysis.progress;

  readonly step = signal<Step>('pick');
  readonly pineapplePath = signal<string | null>(null);
  readonly device = signal<DeviceFacts | null>(null);
  readonly encrypted = signal(false);
  readonly title = signal('');
  readonly password = signal('');
  readonly showPassword = signal(false);
  readonly busy = signal(false);
  readonly pickError = signal<string | null>(null);
  readonly startError = signal<string | null>(null);

  readonly deviceLine = computed(() => {
    const d = this.device() ?? {};
    return [
      d.product_name ?? d.product_type,
      d.product_version ? `iOS ${d.product_version}` : null,
      d.serial,
    ]
      .filter(Boolean)
      .join(' · ');
  });

  readonly phaseText = computed(() => phaseLabel(this.progress().phase));
  readonly isRunning = computed(() => RUNNING_PHASES.includes(this.progress().phase));
  readonly percentText = computed(() => `${Math.round(this.progress().percent)}%`);

  readonly canStart = computed(() => {
    if (this.busy()) return false;
    if (this.title().trim().length === 0) return false;
    return !this.encrypted() || this.password().length > 0;
  });

  constructor() {
    effect(() => {
      this.dialogRef.disableClose = this.isRunning();
    });

    effect(() => {
      if (this.step() === 'progress' && TERMINAL_PHASES.includes(this.progress().phase)) {
        this.step.set('result');
      }
    });
  }

  async chooseFile(): Promise<void> {
    this.pickError.set(null);
    this.busy.set(true);
    try {
      const picked = await this.analysis.choosePineapple();
      if (!picked.ok) return;
      this.pineapplePath.set(picked.path);

      const peek = await this.analysis.peek(picked.path);
      if (!peek.ok) {
        this.pickError.set(peek.error);
        return;
      }
      this.device.set(peek.device);
      this.encrypted.set(peek.encrypted);
      this.title.set(peek.default_title);
      this.step.set('configure');
    } finally {
      this.busy.set(false);
    }
  }

  async start(): Promise<void> {
    const path = this.pineapplePath();
    if (path === null) return;
    this.startError.set(null);
    this.busy.set(true);
    try {
      const folder = await this.analysis.chooseCaseFolder();
      if (!folder.ok) return;

      const password = this.encrypted() ? this.password() : '';
      const started = await this.analysis.startAnalysis(
        path,
        folder.path,
        this.title().trim(),
        password,
      );
      this.step.set('progress');
      if (!started.ok) this.startError.set(started.error);
    } finally {
      this.busy.set(false);
    }
  }

  toggleShowPassword(): void {
    this.showPassword.update((shown) => !shown);
  }

  cancelRun(): void {
    void this.analysis.cancelAnalysis();
  }

  close(): void {
    this.dialogRef.close();
  }
}
