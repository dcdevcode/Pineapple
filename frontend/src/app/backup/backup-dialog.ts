import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatRadioModule } from '@angular/material/radio';
import { BackupService, phaseLabel } from './backup.service';
import { RUNNING_PHASES, type BackupPhase } from './backup.models';

export interface BackupDialogData {
  deviceName: string;
}

type Step = 'confirm' | 'options' | 'progress' | 'result';
type EncryptChoice = 'encrypted' | 'unencrypted';

const TERMINAL_PHASES: readonly BackupPhase[] = ['done', 'error', 'cancelled'];

/**
 * Guides one `.pineapple` logical acquisition: confirm, pick the encryption
 * mode and password, choose where to write the file (native dialog), then watch
 * progress. While the backup runs the dialog cannot be closed — only the
 * explicit Cancel button stops it.
 */
@Component({
  selector: 'app-backup-dialog',
  imports: [
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatRadioModule,
  ],
  templateUrl: './backup-dialog.html',
  styleUrl: './backup-dialog.scss',
})
export class BackupDialog {
  readonly data = inject<BackupDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<BackupDialog>);
  private readonly backup = inject(BackupService);

  readonly progress = this.backup.progress;

  readonly step = signal<Step>('confirm');
  /** null while the pre-flight is in flight. */
  readonly willEncrypt = signal<boolean | null>(null);
  readonly preflightError = signal<string | null>(null);

  readonly encryptChoice = signal<EncryptChoice>('encrypted');
  readonly password = signal('');
  readonly passwordConfirm = signal('');
  readonly showPassword = signal(false);
  /** Busy between "Create image" and the progress view (path dialog + start). */
  readonly busy = signal(false);
  readonly startError = signal<string | null>(null);

  /** The device already encrypts backups, so an existing password is required. */
  readonly needsExistingPassword = computed(() => this.willEncrypt() === true);

  /** Whether this acquisition will produce an encrypted backup. */
  readonly encrypting = computed(
    () => this.needsExistingPassword() || this.encryptChoice() === 'encrypted',
  );

  readonly canSubmit = computed(() => {
    if (this.busy()) return false;
    if (this.needsExistingPassword()) return this.password().length > 0;
    if (this.encryptChoice() === 'unencrypted') return true;
    return this.password().length > 0 && this.password() === this.passwordConfirm();
  });

  readonly phaseText = computed(() => phaseLabel(this.progress().phase));
  readonly isRunning = computed(() => RUNNING_PHASES.includes(this.progress().phase));
  readonly percentText = computed(() => `${Math.round(this.progress().percent)}%`);

  constructor() {
    void this.loadPreflight();

    // Block closing (backdrop / Esc) while the backup is working.
    effect(() => {
      this.dialogRef.disableClose = this.isRunning();
    });

    // Move to the result view once the run reaches a terminal phase.
    effect(() => {
      if (this.step() === 'progress' && TERMINAL_PHASES.includes(this.progress().phase)) {
        this.step.set('result');
      }
    });
  }

  private async loadPreflight(): Promise<void> {
    const result = await this.backup.preflight();
    if (result.ok) {
      this.willEncrypt.set(result.willEncrypt ?? false);
    } else {
      this.preflightError.set(result.error ?? 'Could not read the device state.');
    }
  }

  toContinue(): void {
    this.step.set('options');
  }

  toggleShowPassword(): void {
    this.showPassword.update((shown) => !shown);
  }

  async createImage(): Promise<void> {
    this.startError.set(null);
    this.busy.set(true);
    try {
      const picked = await this.backup.choosePath(this.data.deviceName);
      if (!picked.ok || !picked.path) {
        if (picked.error) this.startError.set(picked.error);
        return;
      }
      const password = this.encrypting() ? this.password() : '';
      const started = await this.backup.start(picked.path, this.encrypting(), password);
      this.step.set('progress');
      if (!started.ok && started.error) this.startError.set(started.error);
    } finally {
      this.busy.set(false);
    }
  }

  cancelRun(): void {
    void this.backup.cancel();
  }

  close(): void {
    this.dialogRef.close();
  }
}
