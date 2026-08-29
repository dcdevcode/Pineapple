import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { SettingsDialog } from './settings-dialog';
import { ThemeService, type ThemePreference } from './theme.service';

describe('SettingsDialog', () => {
  const preference = signal<ThemePreference>('system');
  const setPreference = vi.fn((pref: ThemePreference) => preference.set(pref));

  beforeEach(async () => {
    preference.set('system');
    setPreference.mockClear();
    await TestBed.configureTestingModule({
      imports: [SettingsDialog],
      providers: [
        provideNoopAnimations(),
        { provide: ThemeService, useValue: { preference, setPreference } },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(SettingsDialog);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('lists the sections in the nav rail', async () => {
    const el = await render();
    const items = Array.from(el.querySelectorAll('.settings__nav .mdc-list-item')).map((i) =>
      i.textContent?.trim(),
    );
    expect(items).toEqual(['Theme']);
  });

  it('shows the three theme options with the active one selected', async () => {
    preference.set('dark');
    const el = await render();

    const radios = Array.from(el.querySelectorAll('mat-radio-button input')).map((i) =>
      i.getAttribute('value'),
    );
    expect(radios).toEqual(['light', 'dark', 'system']);

    const checked = el.querySelector('mat-radio-button.mat-mdc-radio-checked');
    expect(checked?.textContent).toContain('Dark');
  });

  it('changes the preference when another option is picked', async () => {
    const el = await render();
    const lightInput = el.querySelector<HTMLInputElement>('mat-radio-button input[value="light"]')!;
    lightInput.click();
    expect(setPreference).toHaveBeenCalledWith('light');
  });
});
