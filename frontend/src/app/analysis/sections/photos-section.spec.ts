import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { PhotosSection } from './photos-section';
import { AnalysisService } from '../analysis.service';

describe('PhotosSection', () => {
  const emptyPage = { rows: [], total: 0, limit: 50, offset: 0 };
  const photos = vi.fn().mockResolvedValue({
    rows: [
      {
        rowid: 1,
        file_id: 'abc',
        filename: 'IMG_0001.HEIC',
        directory: 'DCIM/100APPLE',
        kind: 'image',
        created_utc: null,
        favorite: 1,
        hidden: 0,
        trashed: 0,
        latitude: 1.5,
        longitude: 2.5,
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  });
  const photoAlbums = vi.fn().mockResolvedValue(emptyPage);
  const previewFile = vi.fn().mockResolvedValue(null);
  const dialog = { open: vi.fn() };

  beforeEach(async () => {
    photos.mockClear();
    photoAlbums.mockClear();
    dialog.open.mockClear();
    await TestBed.configureTestingModule({
      imports: [PhotosSection],
      providers: [
        provideNoopAnimations(),
        { provide: MatDialog, useValue: dialog },
        { provide: AnalysisService, useValue: { photos, photoAlbums, previewFile } },
      ],
    }).compileComponents();
  });

  function headers(fixture: { nativeElement: unknown }): (string | undefined)[] {
    return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('th')).map((th) =>
      th.textContent?.trim(),
    );
  }

  it('lists photos first and switches to albums', async () => {
    const fixture = TestBed.createComponent(PhotosSection);
    await fixture.whenStable();

    expect(photos).toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('IMG_0001.HEIC');
    expect(headers(fixture)).toEqual(['Created', 'Filename', 'Kind', 'Flags', 'Location']);

    fixture.componentInstance['view'].set('albums');
    await fixture.whenStable();
    expect(photoAlbums).toHaveBeenCalled();
    expect(headers(fixture)).toEqual(['Title', 'Kind', 'Items', 'From', 'To']);
  });

  it('opens the detail dialog and resolves a thumbnail for a photo row', async () => {
    const fixture = TestBed.createComponent(PhotosSection);
    await fixture.whenStable();

    (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>('tr.mat-mdc-row')!.click();
    await fixture.whenStable();

    expect(previewFile).toHaveBeenCalledWith('abc');
    expect(dialog.open).toHaveBeenCalled();
  });
});
