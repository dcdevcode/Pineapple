import { Injectable, signal } from '@angular/core';

/** User theme choice. `system` follows the OS `prefers-color-scheme`. */
export type ThemePreference = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'pineapple.theme';
const PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system'];

/**
 * Owns the light / dark / system theme preference.
 *
 * The Material theme emits every color token via `light-dark()` (see
 * `styles.scss`); this service picks the active side by setting the CSS
 * `color-scheme` property on `<html>` — or clearing it for `system`, letting the
 * stylesheet's `light dark` baseline defer to the OS. The choice is persisted in
 * `localStorage` and re-applied by an app initializer on startup.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly _preference = signal<ThemePreference>('system');
  readonly preference = this._preference.asReadonly();

  /** Load the stored preference (default `system`) and apply it. */
  init(): void {
    this._preference.set(this.read());
    this.apply();
  }

  /** Change the preference, persist it and repaint. */
  setPreference(pref: ThemePreference): void {
    this._preference.set(pref);
    this.write(pref);
    this.apply();
  }

  private apply(): void {
    const scheme = this._preference();
    if (scheme === 'system') {
      document.documentElement.style.removeProperty('color-scheme');
    } else {
      document.documentElement.style.colorScheme = scheme;
    }
  }

  private read(): ThemePreference {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
    } catch {
      // localStorage can be unavailable (private mode, sandboxed webview).
    }
    return PREFERENCES.includes(stored as ThemePreference) ? (stored as ThemePreference) : 'system';
  }

  private write(pref: ThemePreference): void {
    try {
      localStorage.setItem(STORAGE_KEY, pref);
    } catch {
      // Non-fatal: the preference just will not survive a restart.
    }
  }
}
