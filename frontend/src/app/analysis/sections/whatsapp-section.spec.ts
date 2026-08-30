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
  const whatsappMessages = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 5,
        chat_jid: 'a@s.whatsapp.net',
        chat_name: 'Alice',
        from_me: 0,
        sender: 'a@s.whatsapp.net',
        date_utc: null,
        text: 'hi there',
        media_type: 'text',
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  });
  const dialog = { open: vi.fn() };

  beforeEach(async () => {
    whatsappMessages.mockClear();
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [WhatsappSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
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

  it('renders the message columns and opens a row detail', async () => {
    const fixture = TestBed.createComponent(WhatsappSection);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;

    expect(Array.from(el.querySelectorAll('th')).map((th) => th.textContent?.trim())).toEqual([
      'Date',
      'Chat',
      'Direction',
      'Type',
      'Message',
    ]);
    expect(el.textContent).toContain('hi there');
    expect(el.textContent).toContain('Received');

    el.querySelector<HTMLElement>('tr[mat-row]')!.click();
    await fixture.whenStable();
    expect(dialog.open).toHaveBeenCalled();
  });
});
