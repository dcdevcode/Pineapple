import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { WhatsappSection } from './whatsapp-section';
import { AnalysisService } from '../analysis.service';

describe('WhatsappSection', () => {
  const whatsappChats = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        jid: 'a@s.whatsapp.net',
        name: 'Alice',
        last_message_utc: null,
        message_count: 2,
      },
    ],
    total: 1,
    limit: 500,
    offset: 0,
  });
  const whatsappMessages = vi.fn().mockResolvedValue({ rows: [], total: 0, limit: 50, offset: 0 });

  beforeEach(async () => {
    whatsappMessages.mockClear();
    await TestBed.configureTestingModule({
      imports: [WhatsappSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: { open: vi.fn() } },
        { provide: AnalysisService, useValue: { whatsappChats, whatsappMessages } },
      ],
    }).compileComponents();
  });

  it('loads the chat list and scopes messages by the chosen chat', async () => {
    const fixture = TestBed.createComponent(WhatsappSection);
    await fixture.whenStable();

    expect(whatsappChats).toHaveBeenCalled();
    fixture.componentInstance['chat'].set('a@s.whatsapp.net');
    await fixture.whenStable();

    expect(whatsappMessages).toHaveBeenLastCalledWith(
      expect.objectContaining({ chatJid: 'a@s.whatsapp.net' }),
    );
  });
});
