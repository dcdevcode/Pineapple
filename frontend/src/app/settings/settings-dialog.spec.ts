import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { SettingsDialog } from './settings-dialog';
import { ThemeService } from './theme.service';

describe('SettingsDialog', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsDialog],
      providers: [
        provideNoopAnimations(),
        {
          provide: ThemeService,
          useValue: { preference: signal('system'), setPreference: vi.fn() },
        },
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

  it('renders the active section as its own component', async () => {
    const el = await render();
    expect(el.querySelector('app-theme-settings')).not.toBeNull();
  });
});
