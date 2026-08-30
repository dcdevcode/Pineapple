# Architecture

How Pineapple works, end to end, and *why* it is built this way. Read this
before making a non-trivial change. Companion docs: `UI.md` (the design
system), `CLAUDE.md` (conventions).

Pineapple is an **iOS forensic analysis tool**: a desktop app that inspects an
Apple device over USB and analyses its backups offline. Two guiding
principles shape almost every decision below:

1. **Read-only and non-destructive.** The tool never writes to the device
   except the one unavoidable case — turning on backup encryption for an
   encrypted acquisition — which it always restores afterwards.
2. **Never guess.** When several devices are attached, the tool refuses to
   act rather than pick one. Acting on the wrong device is a worse outcome
   than doing nothing.

---

## 1. Process model

Pineapple is a single OS process:

```
┌─ pywebview native window ──────────────────────────────┐
│  ┌─ WebView ─────────────────────────────────────────┐ │
│  │  Angular app (the production build, or :4200)     │ │
│  │     └── calls window.pywebview.api.<method>(…) ────┼─┼──┐
│  └──────────────────────────────────────────────────┘ │  │
└───────────────────────────────────────────────────────┘  │
                                                           ▼
        pineapple.api.Api  — a plain Python object, one instance,
        bound as js_api=  in pineapple.app.run()
                │
     ┌──────────┼───────────────┬───────────────┬──────────────┐
     ▼          ▼               ▼               ▼              ▼
  devices    SyslogStream   DeviceBackup   AnalysisRun    CaseHandle
 (asyncio)   ── all long-lived work runs on ──   the open case's
             pineapple.session.session           analysis.db + backup
```

- **`pineapple.app`** opens the window. `--dev` points it at
  `http://localhost:4200`; otherwise it serves
  `frontend/dist/pineapple-frontend/browser/` with pywebview's built-in HTTP
  server and exits with a clear message if that build is missing.
- **`pineapple.api.Api`** is the whole bridge surface. pywebview turns every
  public method into `window.pywebview.api.<name>` verbatim, so the methods
  are `snake_case` and their names are an API contract with the frontend
  (`frontend/src/app/device/pywebview.d.ts` is the hand-written mirror).
- pywebview invokes bridge methods on **worker threads from a small pool**,
  with **no event loop** on them. Everything downstream is shaped by that
  fact.

### The bridge is synchronous; the device layer is async

`pymobiledevice3` v11 is async-only, so `pineapple.devices` is async with no
sync wrappers. The bridge closes the gap two ways:

- **Short calls** (list devices, read info, preflight): `asyncio.run(...)` —
  spin up a loop, run one coroutine, tear it down. Fine for a sub-second
  call.
- **Long-lived work** (syslog stream, a backup, an analysis run): cannot use
  `asyncio.run` because the work must outlive the bridge call and hold a
  device connection across many calls. It runs on the one shared loop in
  `pineapple.session`.

### Response envelopes

The frontend has to distinguish three shapes, all documented on the `Api`
methods:

| Shape | Used by |
| --- | --- |
| `{"ok": True, …}` / `{"ok": False, "error": "…"}` | most methods — the frontend unwraps or throws |
| a raw progress snapshot (no `ok`) | `read_syslog`, `read_backup_progress`, `read_analysis_progress` |
| `{"status": "none" \| "one" \| "multiple"}` | `connected_device` only |

Every bridge method that can raise catches broadly and returns an `ok: False`
envelope — an exception must never propagate into pywebview.

---

## 2. `DeviceSession` — the shared connector

`pineapple.session.DeviceSession` owns **one `asyncio` event loop running on a
daemon thread**, created once at import as the module singleton `session`.

| Method | Purpose |
| --- | --- |
| `run(coro)` | schedule on the loop, block for the result (used for short async calls that still need *the* loop) |
| `spawn(coro)` | create a background `Task` on the loop thread, return it (creating a task from another thread is not safe, so this hops via `call_soon_threadsafe`) |
| `cancel(task)` | request cancellation of a spawned task |
| `drain(task, timeout)` | after `cancel`, block up to `timeout` for the task to unwind, ignoring its outcome |
| `close()` | stop the loop + join the thread (tests; the singleton runs for the process lifetime) |

It is deliberately **minimal — a shared connector, not a service registry**.
Consumers open their own lockdown connections on the loop and manage their own
tasks. There is exactly one loop because the streaming features each hold a
device connection and the device tolerates only so much concurrency.

---

## 3. The long-lived job pattern

`SyslogStream`, `DeviceBackup` and `AnalysisRun` are three variations on one
shape. They are **not** unified into a base class (see `CLAUDE.md` on
premature abstraction), but knowing the shape makes all three readable:

- **State.** A `_Progress` dataclass (phase / percent / note / error /
  running, plus job-specific fields). `progress()` returns a plain-dict
  snapshot under `_state_lock`; the frontend polls it.
- **Two locks.** `_op_lock` serialises `start` / `stop` / `cancel` so a
  restart cannot race a previous teardown. `_state_lock` guards every read
  and write of the progress state (it is written on the loop thread and read
  on a worker thread).
- **Cancellation.** A `threading.Event` (`_cancelled`). The actual work runs
  in a worker thread (`run_in_executor` / `asyncio.to_thread`) that checks
  the event **between phases** — cancellation is cooperative and only takes
  effect at a checkpoint, never mid-operation.
- **Teardown.** `_teardown()` sets the event, calls `session.cancel(task)`,
  then `session.drain(task, TEARDOWN_TIMEOUT)`. A slow teardown must never
  hang the UI, hence the timeout; cleanup that still needs to happen
  (restoring device encryption) is `asyncio.shield`-ed so it finishes in the
  background while the frontend keeps polling until `running` goes false.
- **Rollback.** On cancel or failure the job removes whatever partial output
  it wrote (a half-written archive, a partial `analysis.db` + descriptor).

---

## 4. Reading the iPhone (`pineapple.devices`, `pineapple.syslog`)

### Presence

`connected_devices()` talks **only to the local usbmuxd daemon** — no device
contact — so it is cheap enough for the frontend to poll every 2 s. It
returns `[]` when usbmuxd is unavailable. `single_device_udid()` returns the
UDID only when **exactly one** device is attached; this is the one place the
"never auto-pick" policy lives, and every single-device feature routes
through it.

### Pairing and info

`get_device_info(udid)` opens a **lockdown** connection
(`create_using_usbmux(autopair=False)`), which requires the user to have
tapped **"Trust this computer"** on the device. It projects
`lockdown.all_values` down to the fixed `INFO_FIELDS` list and always closes
the connection. Unpaired or unreachable → it raises; the bridge turns that
into `{"ok": False}` and the frontend shows the "needs trust" state, retrying
on every poll so granting trust is picked up without replugging.

### Live syslog

`SyslogStream` resolves the single device, opens lockdown, and spawns an
`OsTraceService.syslog()` async-iterator reader on `session`. Entries are
flattened to `SyslogLine` and pushed into a `deque(maxlen=5000)` under a lock;
`read()` drains it and reports `running` / `dropped` / `error`.

The reader runs inside `async with OsTraceService(...)`. That context manager
**must** close the `os_trace_relay` service socket on exit — including on
cancellation — because leaking it makes the device refuse the next stream, so
reopening the viewer would silently fail. `stop()` therefore blocks (via
`drain`) until the reader has finished closing its connections.

---

## 5. Creating a backup (`pineapple.backup`)

`DeviceBackup.start()` runs a full **MobileBackup2** backup on `session` into
a temp staging dir, then packs `staging/<udid>/` into the chosen path as an
**uncompressed** (`ZIP_STORED`) zip named `*.pineapple`. Phases:
`preparing` → `backing_up` → `packaging` → (`restoring_encryption`) → `done`
/ `error` / `cancelled`, with `percent` fed by MobileBackup2's progress
callback.

### Encryption is a *device* setting

Passing a password to `Mobilebackup2Service.backup` does **not** turn
encryption on — `WillEncrypt` is a device-wide flag. So for an encrypted
acquisition on a device that does not already encrypt, `DeviceBackup`:

1. calls `change_password(new=…)` to enable it (`_enable_encryption_if_needed`);
2. runs the backup;
3. **always** calls `change_password(old=…)` to restore the original state —
   on success, failure and cancel alike. The restore is `asyncio.shield`-ed
   so a cancel still runs it, and `_we_enabled_encryption` is set *before*
   the enable call so a cancel mid-change still triggers the restore.

If the restore fails, the run still completes but the final `note` warns that
the device is left with encryption on and the chosen password.

### One service context per operation

Each device operation (enable / backup / restore) opens its **own**
`Mobilebackup2Service` context. The `com.apple.mobilebackup2` session is
single-use: one DeviceLink operation, then `DLMessageDisconnect`. Reusing one
instance runs the second operation on a dead session.

---

## 6. The `.pineapple` archive

A `.pineapple` file is a plain **uncompressed zip** whose entries are rooted
at the device UDID:

```
<udid>/Info.plist
<udid>/Manifest.plist
<udid>/Manifest.db
<udid>/Status.plist
<udid>/aa/aa11bb22…        ← backup file blobs, named by SHA-1(domain-relativePath)
<udid>/ab/…
```

Uncompressed so a reader can `mmap`/seek into it and so packaging is fast on a
multi-GB backup. The layout is exactly what `pymobiledevice3` would restore
from.

The three root plists (`Info` / `Manifest` / `Status`) are **never
encrypted**, so `archive.peek()` reads device facts straight out of the zip
without unpacking. Each is XML or binary — `plistlib.loads` handles both.
`archive.extract()` unpacks everything as-is; encrypted blobs stay encrypted
on disk.

---

## 7. The analysis pipeline (`pineapple.analysis`)

`AnalysisRun` runs this on `session` while the frontend polls `progress()`.
Phases and their percent ceilings: `extracting` (40) → `opening` (55) →
`indexing` (70) → `parsing` (95) → `writing_descriptor` → `done`. The worker
thread checks `_cancelled` between phases; on cancel or any failure
`_cleanup_partial` removes `analysis.db` and the descriptor.

### 7.1 Peek and extract

`archive.peek()` → `BackupMetadata` (device, `is_encrypted`, apps) from the
plists. `archive.extract()` → `<case>/backup/<udid>/`.

### 7.2 Open a reader (`analysis.reader`)

`open_reader()` returns, based on `Manifest.plist`'s `IsEncrypted`:

- **`PlainBackupReader`** — everything is already in the clear; it just copies
  `Manifest.db` and the requested blobs.
- **`EncryptedBackupReader`** — wraps `iphone_backup_decrypt.EncryptedBackup`.
  Every blob and `Manifest.db` itself is AES-encrypted with per-file keys
  wrapped in the keybag from `Manifest.plist`. A wrong password raises
  (mapped to `AnalysisError`).

Both satisfy the `BackupReader` protocol: `manifest_connection()`,
`extract_db()` (with `-wal` / `-shm` sidecars, so a parser sees recent rows),
`extract_file()`, `read_bytes()`, `close()`.

### 7.3 Index (`parsers.index_*`)

Straight from `Manifest.db` and the plists, not from a source app DB:
`index_backup_info` (one `backup_info` row), `index_apps`, `index_files`
(decoding each `Files.file` `NSKeyedArchiver` blob via `analysis.mbfile` for
size / timestamps / mode / symlink target).

### 7.4 Parse the artifacts (`parsers/`, `ARTIFACT_PARSERS`)

The runner iterates `ARTIFACT_PARSERS` in order. Each `ParserSpec` says where
its source DB lives (`relative_path`, `domain`) and how to parse it. The
reader extracts that one DB into `<case>/decrypted/`; the parser opens it
read-only via `_common.read_source(path, label)` (which maps `sqlite3.Error`
→ `ArtifactUnreadable`) and writes rows into `analysis.db`.

| Parser | Source | Notes |
| --- | --- | --- |
| `messages` | `HomeDomain/Library/SMS/sms.db` | iOS 16+ leaves `text` NULL and keeps the body in `attributedBody` — recovered (§8) |
| `calls` | `…/CallHistoryDB/CallHistory.storedata` | Core Data; **`encrypted_only`** |
| `contacts` | `…/AddressBook/AddressBook.sqlitedb` | names + `ABMultiValue` phones/emails |
| `notes` | `AppDomainGroup-group.com.apple.notes/NoteStore.sqlite` | body is gzip + protobuf (§8) |
| `photos` | `CameraRollDomain/Media/PhotoData/Photos.sqlite` | Core Data; fills `photos` + `photo_albums`; each row keeps the asset's Manifest file id for preview |
| `calendar` | `…/Library/Calendar/Calendar.sqlitedb` | `CalendarItem` + `Calendar` + `Location`; `Participant` rows joined into `invitees` (`count_key`) |
| `voicemail` | `…/Library/Voicemail/voicemail.db` | caller / duration / `trashed_date`; transcription column picked up when present |
| `safari_history` | `…/Safari/History.db` | **`encrypted_only`** |
| `safari_bookmarks` | `…/Safari/Bookmarks.db` | self-referential table, `type` 1 = bookmark |
| `whatsapp` | `AppDomainGroup-group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite` | fills `whatsapp_chats` + `whatsapp_messages` (`count_key`) |

**Tolerance.** A missing or damaged source DB is recorded in `skipped`, never
fatal. **`encrypted_only`.** iOS keeps call history and Safari out of
*unencrypted* backups, so their absence there is expected and the skip note
says so.

### 7.5 Write the descriptor

`_write_descriptor` writes `<case>/<title>.json` (`CaseDescriptor`: title,
device, source path + SHA-256, parse counts + skips, tool + schema version)
and mirrors the essentials into `analysis.db`'s `case_meta` for tools that
only open the DB.

---

## 8. Decoding what Apple stores

- **iMessage `attributedBody`** (`parsers/attributed_body.py`): an
  `NSMutableAttributedString` serialised in Apple's legacy *typedstream*
  format (`NSArchiver`, not a keyed archive). `typedstream.unarchive_from_data`
  then walk `.contents[].value` for the first `NSString`. Best-effort → `None`.
- **Apple Notes body** (`parsers/notes.py`): `ZICNOTEDATA.ZDATA` is a
  gzip-compressed protobuf. We only want the plain text, at
  `Document(2) → Note(3) → note_text(2)`; a hand-rolled varint reader walks
  the length-delimited fields. Best-effort; `ZSNIPPET` is the fallback.
- **Timestamps** (`parsers/_common.py`): Cocoa "absolute time" is seconds
  since 2001-01-01 UTC, but iOS 11+ stores some columns in nanoseconds — a
  magnitude check picks the scale. Unix epoch columns go through
  `unix_to_iso`. **Every timestamp in `analysis.db` is an ISO-8601 UTC
  string**, so the frontend never does timezone maths.
- **Core Data** stores (`calls`, `notes`, `whatsapp`) have `Z`-prefixed
  tables and `Z_PK` primary keys.

---

## 9. The case folder (`analysis.descriptor`, `analysis.case`)

Everything a case needs is in one folder the user picks:

```
<case>/<title>.json     the descriptor — source of truth for reopening
<case>/analysis.db      the results (schema v3)
<case>/backup/<udid>/   the archive extracted as-is (encrypted blobs stay encrypted)
<case>/decrypted/       Manifest.db + the source DBs the parsers needed
```

- **`<title>`** defaults to the device serial; `find_descriptor` requires
  exactly one `*.json` in the folder (one analysis per folder).
- **Schema is v3.** `load_case` rejects a mismatch — re-analyse older cases.
- **`CaseHandle`** answers the frontend's paginated read queries. It opens a
  **fresh short-lived `sqlite3` connection per query** (`_connect`), because
  pywebview answers bridge calls on a thread pool and a SQLite connection may
  only be used on the thread that created it — a persistent connection would
  break the moment a second call landed on a different worker.
- **File access.** `CaseHandle` also lends read access to the backup itself:
  `preview_file` (size-capped at `PREVIEW_MAX_BYTES` = 5 MB, classified
  image / plist / text / binary / unavailable) and `extract_file` (writes one
  file out). For an encrypted backup that needs the password, it is passed to
  `load_case` / `set_password` and **held only in RAM**. The `Api` keeps that
  key across `start_analysis` / `open_case` so a just-finished encrypted case
  can read its own files without prompting again.

---

## 10. Error model

- **`AnalysisError`** — a problem the user can act on (malformed archive,
  wrong password, missing manifest, schema mismatch). Raised instead of
  leaking library-specific exceptions.
- **`ArtifactUnreadable(AnalysisError)`** — one source DB could not be parsed;
  the run records it as skipped and carries on.
- At the bridge, `AnalysisError` and any other exception both become
  `{"ok": False, "error": str(e)}`. `read_analysis_progress` turns a
  post-`done` `load_case` failure into an `error` snapshot rather than
  silently never opening the browser.

---

## 11. Frontend architecture (`frontend/src/app`)

Angular 22, **zoneless** (no `zone.js`; `provideZonelessChangeDetection()` in
`app.config.ts`), fully signal-based. Standalone components, `inject()`,
`input.required`, `@if` / `@for` / `@switch`.

### The polling-service pattern

`DeviceService`, `SyslogService`, `BackupService`, `AnalysisService` all share
a shape (again, not abstracted): a `signal` of state, a `setInterval` poll
loop, a **generation counter** bumped on every `start` so a late poll from a
superseded run bails out, an `IDLE` constant, and an **idle no-op when
`window.pywebview` is absent** so the app also runs in a plain browser
(`pnpm start`). `poll()` is exposed so a test can await one iteration.

- `DeviceService` polls `connected_device()` every 2 s; fetches full info once
  per device, retrying while `unpaired`.
- `SyslogService` / `BackupService` / `AnalysisService` poll their
  `read_*_progress` every 400–500 ms while their dialog is open, and stop when
  the backend reports the run ended.

### The Analysis tab

`AnalysisService.summary()` being non-null is what switches the tab from the
**launcher** to the **case browser** (a nav-rail over Overview / Apps / Files
/ Messages / Calls / Contacts / Notes / Safari / WhatsApp). `AnalysisDialog`
is the pick → configure → progress wizard; on `done` the service calls
`open_case` and the tab flips.

`ArtifactTable` is a generic `mat-table` + `mat-paginator` that **owns its own
fetch loop** — it re-runs the injected `fetchPage` whenever the page,
debounced search term, or `scope` input changes, and renders loading / empty /
error. A searchable table projects a `[tableFilter]` control into its toolbar.
A row click opens `RecordDetailDialog` (every field, full text, a copy icon
per field; Files rows add a content preview + Extract). The four simple
tables (apps / messages / calls / contacts) are configured inline in
`analysis.ts`; Files / Notes / Safari / WhatsApp have their own section
components because they carry extra controls (domain filter, unlock banner,
history↔bookmarks toggle, chat scope).

### `pywebview.d.ts`

The hand-written TypeScript interface for the whole `Api`. Keep it in lockstep
with `pineapple/api.py` — it is the only thing type-checking the bridge calls.

---

## 12. Testing

Neither suite touches hardware.

- **Backend** (`uv run pytest`): `tests/support.py` fakes the
  `pymobiledevice3` / `webview` boundary; `tests/analysis_support.py` builds a
  **tiny real on-disk MobileBackup2 backup** (real SQLite source DBs, a real
  `attributedBody` sample, a real Notes protobuf) and a `.pineapple` from it,
  and fakes `iphone_backup_decrypt` with `FakeEncryptedBackup` (an
  "encrypted" backup is just one whose `Manifest.plist` says so). The
  long-lived jobs are driven by polling `progress()` to a terminal phase.
- **Frontend** (`pnpm test`, vitest): services are tested by installing a
  partial bridge on `window.pywebview` and awaiting `poll()`; components with
  `TestBed` + a faked service.

CI (`.github/workflows/ci.yml`) runs ruff / mypy-strict / pytest and
prettier / eslint / vitest / build on every push and PR.
