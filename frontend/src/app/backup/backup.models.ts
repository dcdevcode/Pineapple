/** Phases the backend `DeviceBackup` moves through, mirrored from `backup.py`. */
export type BackupPhase =
  | 'idle'
  | 'preparing'
  | 'backing_up'
  | 'packaging'
  | 'restoring_encryption'
  | 'done'
  | 'error'
  | 'cancelled';

/** Result of `backup_preflight`: does the device already encrypt its backups. */
export interface BackupPreflight {
  ok: boolean;
  willEncrypt?: boolean;
  error?: string;
}

/** Snapshot from `read_backup_progress`. */
export interface BackupProgress {
  phase: BackupPhase;
  percent: number;
  output_path: string | null;
  error: string | null;
  note: string | null;
  running: boolean;
}

/** Result of `choose_backup_path` / `start_backup`. */
export interface BackupActionResult {
  ok: boolean;
  error?: string;
  path?: string;
}

/** Phases where the acquisition is still working and must not be interrupted. */
export const RUNNING_PHASES: readonly BackupPhase[] = [
  'preparing',
  'backing_up',
  'packaging',
  'restoring_encryption',
];
