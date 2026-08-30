import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { Page, PageQuery, WhatsappChatRow } from '../analysis.models';

/** The WhatsApp section: pick a chat to scope the message table. */
@Component({
  selector: 'app-whatsapp-section',
  imports: [ArtifactTable, FormsModule, MatFormFieldModule, MatSelectModule],
  templateUrl: './whatsapp-section.html',
  styleUrl: './whatsapp-section.scss',
})
export class WhatsappSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly chat = signal('');
  protected readonly chats = signal<WhatsappChatRow[]>([]);

  protected readonly columns: readonly ColumnDef[] = [
    { key: 'date_utc', label: 'Date', format: (r) => localTime(r['date_utc']) },
    { key: 'chat_name', label: 'Chat' },
    { key: 'from_me', label: 'Direction', format: (r) => (r['from_me'] ? 'Sent' : 'Received') },
    { key: 'media_type', label: 'Type' },
    { key: 'text', label: 'Message' },
  ];

  protected readonly fetch: FetchPage = async (q: PageQuery) =>
    (await this.analysis.whatsappMessages({
      ...q,
      chatJid: this.chat() || undefined,
    })) as unknown as Page<TableRow>;

  protected readonly detail: DetailBuilder = (r) => [
    ...field('Date', localTime(r['date_utc'])),
    ...field('Chat', r['chat_name']),
    ...field('Direction', r['from_me'] ? 'Sent' : 'Received'),
    ...field('Sender', r['sender']),
    ...field('Type', r['media_type']),
    ...field('Message', r['text'], true),
  ];

  protected readonly title = (r: TableRow): string =>
    String(r['chat_name'] || r['sender'] || 'Message');

  constructor() {
    void this.loadChats();
  }

  private async loadChats(): Promise<void> {
    try {
      this.chats.set((await this.analysis.whatsappChats({ limit: 500, offset: 0 })).rows);
    } catch {
      this.chats.set([]);
    }
  }
}
