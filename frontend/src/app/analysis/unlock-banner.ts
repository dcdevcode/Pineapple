import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { AnalysisService } from './analysis.service';

/**
 * The encrypted-backup unlock prompt for the open case. Shown in the case-browser
 * shell on every section while the backup is encrypted and its key is not held;
 * hides itself the moment the key is supplied (the summary refreshes).
 */
@Component({
  selector: 'app-unlock-banner',
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule],
  templateUrl: './unlock-banner.html',
  styleUrl: './unlock-banner.scss',
})
export class UnlockBanner {
  private readonly analysis = inject(AnalysisService);

  protected readonly locked = computed(() => {
    const summary = this.analysis.summary();
    return !!summary?.is_encrypted && !summary.files_unlocked;
  });

  protected readonly password = signal('');
  protected readonly showPassword = signal(false);
  protected readonly unlocking = signal(false);
  protected readonly unlockError = signal<string | null>(null);

  protected toggleShowPassword(): void {
    this.showPassword.update((shown) => !shown);
  }

  protected async unlock(): Promise<void> {
    this.unlocking.set(true);
    this.unlockError.set(null);
    try {
      const result = await this.analysis.unlock(this.password());
      if (!result.ok) this.unlockError.set(result.error ?? 'Wrong key.');
      else this.password.set('');
    } finally {
      this.unlocking.set(false);
    }
  }
}
