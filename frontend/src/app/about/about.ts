import { Component } from '@angular/core';

/** One credited project shown in the About tab's Thanks list. */
interface Credit {
  name: string;
  url: string;
  blurb: string;
}

/**
 * The About tab: the wordmark, the author line, and a thank-you to the projects
 * that do the real forensic work — device access, backup decryption, the
 * typedstream decode and the desktop window.
 */
@Component({
  selector: 'app-about',
  templateUrl: './about.html',
  styleUrl: './about.scss',
})
export class About {
  readonly credits: readonly Credit[] = [
    {
      name: 'pymobiledevice3',
      url: 'https://github.com/doronz88/pymobiledevice3',
      blurb:
        'Talks to the iPhone over USB: lockdown, the MobileBackup2 acquisition and the live syslog stream.',
    },
    {
      name: 'iphone_backup_decrypt',
      url: 'https://github.com/jsharkey13/iphone_backup_decrypt',
      blurb: 'Unlocks and decrypts encrypted iOS backups so their databases and files can be read.',
    },
    {
      name: 'python-typedstream',
      url: 'https://github.com/dgelessus/python-typedstream',
      blurb: 'Decodes the typedstream attributedBody blobs that hold iOS 16+ iMessage text.',
    },
    {
      name: 'pywebview',
      url: 'https://pywebview.flowrl.com/',
      blurb: 'Hosts the native desktop window the app runs in.',
    },
  ];
}
