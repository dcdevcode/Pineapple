import {
  AfterViewInit,
  Component,
  DestroyRef,
  afterRenderEffect,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { CdkVirtualScrollViewport, ScrollingModule } from '@angular/cdk/scrolling';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { SyslogService, formatSyslogLines } from './syslog.service';
import type { SyslogLine } from './syslog.models';

export interface SyslogDialogData {
  deviceName: string;
}

/** Live syslog viewer shown in a large modal, opened from the Device tab. */
@Component({
  selector: 'app-syslog-dialog',
  imports: [
    FormsModule,
    ScrollingModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  templateUrl: './syslog-dialog.html',
  styleUrl: './syslog-dialog.scss',
})
export class SyslogDialog implements AfterViewInit {
  private readonly syslog = inject(SyslogService);
  readonly data = inject<SyslogDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<SyslogDialog>);
  private readonly destroyRef = inject(DestroyRef);

  private readonly viewport = viewChild.required(CdkVirtualScrollViewport);

  readonly allLines = this.syslog.lines;
  readonly running = this.syslog.running;
  readonly paused = this.syslog.paused;
  readonly error = this.syslog.error;
  readonly dropped = this.syslog.dropped;
  readonly processes = this.syslog.processes;

  readonly textFilter = signal('');
  readonly processFilter = signal('');
  /** Autoscroll unless the user has scrolled away from the bottom. */
  private readonly followTail = signal(true);

  readonly filteredLines = computed<SyslogLine[]>(() => {
    const needle = this.textFilter().toLowerCase().trim();
    const process = this.processFilter();
    return this.syslog.lines().filter((line) => {
      if (process && line.process !== process) return false;
      if (!needle) return true;
      return (
        line.message.toLowerCase().includes(needle) ||
        line.process.toLowerCase().includes(needle) ||
        (line.label?.toLowerCase().includes(needle) ?? false)
      );
    });
  });

  constructor() {
    void this.syslog.start();
    this.destroyRef.onDestroy(() => void this.syslog.stop());

    // After each render, keep the newest line in view unless the user has
    // scrolled up. afterRenderEffect runs once the viewport exists and has the
    // new item count, so no manual deferral is needed.
    afterRenderEffect(() => {
      const lines = this.filteredLines();
      if (this.followTail() && lines.length > 0) {
        this.viewport().scrollToIndex(lines.length - 1, 'auto');
      }
    });
  }

  ngAfterViewInit(): void {
    this.viewport()
      .elementScrolled()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        const distanceFromBottom = this.viewport().measureScrollOffset('bottom');
        this.followTail.set(distanceFromBottom < 40);
      });
  }

  formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
  }

  isSevere(level: string): boolean {
    return level === 'ERROR' || level === 'FAULT';
  }

  togglePause(): void {
    this.syslog.togglePause();
  }

  clear(): void {
    this.syslog.clear();
  }

  async export(): Promise<void> {
    await this.syslog.export(formatSyslogLines(this.filteredLines()));
  }

  close(): void {
    this.dialogRef.close();
  }
}
