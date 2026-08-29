import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { SettingsMenu } from './settings-menu';
import { ThemeService, type ThemePreference } from './theme.service';

describe('SettingsMenu', () => {
  const preference = signal<ThemePreference>('system');
  const setPreference = vi.fn((pref: ThemePreference) => preference.set(pref));

  beforeEach(async () => {
    preference.set('system');
    setPreference.mockClear();
    await TestBed.configureTestingModule({
      imports: [SettingsMenu],
      providers: [
        provideNoopAnimations(),
        { provide: ThemeService, useValue: { preference, setPreference } },
      ],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(SettingsMenu);
    await fixture.whenStable();
    return fixture;
  }

  function menuItems(): HTMLButtonElement[] {
    return Array.from(document.querySelectorAll('.mat-mdc-menu-item'));
  }

  afterEach(() => {
    // Close any menu overlay left open between tests.
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => (el.innerHTML = ''));
  });

  it('exposes a labelled settings trigger', async () => {
    const fixture = await render();
    const trigger = fixture.nativeElement.querySelector('button');
    expect(trigger?.getAttribute('aria-label')).toBe('Settings');
  });

  it('lists the three theme options when opened', async () => {
    const fixture = await render();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();

    expect(menuItems().map((b) => b.textContent?.trim())).toEqual(['Light', 'Dark', 'System']);
  });

  it('marks the active preference as checked', async () => {
    preference.set('dark');
    const fixture = await render();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();

    const checked = menuItems().filter((b) => b.getAttribute('aria-checked') === 'true');
    expect(checked.map((b) => b.textContent?.trim())).toEqual(['Dark']);
  });

  it('changes the preference when an option is clicked', async () => {
    const fixture = await render();
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();

    menuItems()
      .find((b) => b.textContent?.trim() === 'Light')!
      .click();
    expect(setPreference).toHaveBeenCalledWith('light');
  });
});
