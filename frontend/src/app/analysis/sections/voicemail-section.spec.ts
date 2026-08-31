import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { VoicemailSection } from './voicemail-section';
import { AnalysisService } from '../analysis.service';

describe('VoicemailSection', () => {
  const dialog = { open: vi.fn() };
  const voicemail = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        sender: '+15551234567',
        received_utc: null,
        duration_seconds: 23,
        trashed: 0,
        transcript: 'Call me back',
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  });

  beforeEach(async () => {
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [VoicemailSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { voicemail } },
      ],
    }).compileComponents();
  });

  it('renders voicemails and opens the detail with the transcript', async () => {
    const fixture = TestBed.createComponent(VoicemailSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('+15551234567');
    el.querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    const data = dialog.open.mock.calls[0][1].data;
    expect(data.fields).toContainEqual({ label: 'Transcript', value: 'Call me back', long: true });
  });
});
