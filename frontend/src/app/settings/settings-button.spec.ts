import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { SettingsButton } from './settings-button';
import { SettingsDialog } from './settings-dialog';

describe('SettingsButton', () => {
  const open = vi.fn();

  beforeEach(async () => {
    open.mockClear();
    await TestBed.configureTestingModule({
      imports: [SettingsButton],
      providers: [{ provide: MatDialog, useValue: { open } }],
    }).compileComponents();
  });

  async function render() {
    const fixture = TestBed.createComponent(SettingsButton);
    await fixture.whenStable();
    return fixture;
  }

  it('exposes a labelled settings trigger', async () => {
    const fixture = await render();
    const trigger = fixture.nativeElement.querySelector('button');
    expect(trigger?.getAttribute('aria-label')).toBe('Settings');
  });

  it('opens the settings dialog when clicked', async () => {
    const fixture = await render();
    fixture.nativeElement.querySelector('button').click();
    expect(open).toHaveBeenCalledWith(
      SettingsDialog,
      expect.objectContaining({ autoFocus: false }),
    );
  });
});
