import { NgTemplateOutlet } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import type { FilePreview } from './analysis.models';

/** One label/value pair shown in the detail dialog. */
export interface DetailField {
  label: string;
  value: string;
  /** Render in a scrollable block rather than inline (long text, bodies). */
  long?: boolean;
}

export interface RecordDetailData {
  title: string;
  fields: DetailField[];
  /** Present for a Files row: the file's content preview. */
  preview?: FilePreview | null;
  /** Present for a Files row: save the file to disk (native dialog). */
  extract?: (() => Promise<{ ok: boolean; path?: string; error?: string }>) | null;
}

const COPIED_CLEAR_MS = 1500;

/**
 * The full record behind one artifact-table row: every field, untruncated, each
 * with a copy button. For a Files row it also shows a content preview and an
 * Extract action.
 */
@Component({
  selector: 'app-record-detail-dialog',
  imports: [NgTemplateOutlet, MatButtonModule, MatDialogModule, MatTooltipModule],
  templateUrl: './record-detail-dialog.html',
  styleUrl: './record-detail-dialog.scss',
})
export class RecordDetailDialog {
  protected readonly data = inject<RecordDetailData>(MAT_DIALOG_DATA);

  protected readonly copied = signal<string | null>(null);
  protected readonly extracting = signal(false);
  protected readonly extractStatus = signal<string | null>(null);

  protected async copy(field: DetailField): Promise<void> {
    try {
      await navigator.clipboard.writeText(field.value);
      this.copied.set(field.label);
      setTimeout(() => this.copied.set(null), COPIED_CLEAR_MS);
    } catch {
      this.copied.set(null);
    }
  }

  protected imageSrc(preview: FilePreview): string {
    return preview.kind === 'image' ? `data:${preview.mime};base64,${preview.data_base64}` : '';
  }

  protected plistText(preview: FilePreview): string {
    return preview.kind === 'plist' ? JSON.stringify(preview.json, null, 2) : '';
  }

  protected async runExtract(): Promise<void> {
    if (!this.data.extract || this.extracting()) return;
    this.extracting.set(true);
    this.extractStatus.set(null);
    try {
      const result = await this.data.extract();
      if (result.ok && result.path) this.extractStatus.set(`Saved to ${result.path}`);
      else if (result.error) this.extractStatus.set(result.error);
    } finally {
      this.extracting.set(false);
    }
  }
}
