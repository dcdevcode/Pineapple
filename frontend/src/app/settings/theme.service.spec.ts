import { TestBed } from '@angular/core/testing';
import { ThemeService } from './theme.service';

const STORAGE_KEY = 'pineapple.theme';

describe('ThemeService', () => {
  let service: ThemeService;

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.style.removeProperty('color-scheme');
    service = TestBed.inject(ThemeService);
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.style.removeProperty('color-scheme');
  });

  it('defaults to "system" and applies no inline color-scheme', () => {
    service.init();
    expect(service.preference()).toBe('system');
    expect(document.documentElement.style.colorScheme).toBe('');
  });

  it('applies an explicit choice to <html> and persists it', () => {
    service.setPreference('dark');
    expect(service.preference()).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('dark');
  });

  it('restores a stored preference on init()', () => {
    localStorage.setItem(STORAGE_KEY, 'light');
    service.init();
    expect(service.preference()).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('clears the inline color-scheme when switching back to "system"', () => {
    service.setPreference('dark');
    service.setPreference('system');
    expect(document.documentElement.style.colorScheme).toBe('');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('system');
  });

  it('falls back to "system" for an invalid stored value', () => {
    localStorage.setItem(STORAGE_KEY, 'sepia');
    service.init();
    expect(service.preference()).toBe('system');
  });
});
