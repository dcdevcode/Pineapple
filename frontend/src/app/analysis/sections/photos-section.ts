import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { AnalysisService } from '../analysis.service';
import { ArtifactTable, type ColumnDef, type FetchPage, type TableRow } from '../artifact-table';
import { field, localTime, type DetailBuilder } from '../detail-fields';
import type { FilePreview, Page, PageQuery } from '../analysis.models';

type View = 'photos' | 'albums';

/** Marks favourite / hidden / trashed state in one short cell. */
function photoFlags(row: TableRow): string {
  return [
    row['favorite'] ? '★' : '',
    row['hidden'] ? 'hidden' : '',
    row['trashed'] ? 'trashed' : '',
  ]
    .filter(Boolean)
    .join(' ');
}

function location(row: TableRow): string {
  const lat = row['latitude'];
  const lon = row['longitude'];
  return lat != null && lon != null ? `${lat}, ${lon}` : '';
}

function dimensions(row: TableRow): string {
  return row['width'] && row['height'] ? `${row['width']} × ${row['height']}` : '';
}

/**
 * The Photos section: the camera roll, switched between the asset list and the
 * albums by a toggle. An asset row opens its metadata plus a preview of the real
 * image (via its Manifest file id).
 */
@Component({
  selector: 'app-photos-section',
  imports: [ArtifactTable, FormsModule, MatButtonToggleModule],
  templateUrl: './photos-section.html',
  styleUrl: './photos-section.scss',
})
export class PhotosSection {
  private readonly analysis = inject(AnalysisService);

  protected readonly view = signal<View>('photos');

  private readonly photoColumns: readonly ColumnDef[] = [
    { key: 'created_utc', label: 'Created', format: (r) => localTime(r['created_utc']) },
    { key: 'filename', label: 'Filename' },
    { key: 'kind', label: 'Kind' },
    { key: 'flags', label: 'Flags', format: photoFlags },
    { key: 'location', label: 'Location', format: location },
  ];
  private readonly albumColumns: readonly ColumnDef[] = [
    { key: 'title', label: 'Title' },
    { key: 'kind', label: 'Kind' },
    { key: 'count', label: 'Items', numeric: true },
    { key: 'start_utc', label: 'From', format: (r) => localTime(r['start_utc']) },
    { key: 'end_utc', label: 'To', format: (r) => localTime(r['end_utc']) },
  ];

  private readonly fetchPhotos: FetchPage = async (q: PageQuery) =>
    (await this.analysis.photos(q)) as unknown as Page<TableRow>;
  private readonly fetchAlbums: FetchPage = async (q: PageQuery) =>
    (await this.analysis.photoAlbums(q)) as unknown as Page<TableRow>;

  private readonly photoDetail: DetailBuilder = (r) => [
    ...field('Filename', r['filename']),
    ...field('Directory', r['directory']),
    ...field('Kind', r['kind']),
    ...field('Created', localTime(r['created_utc'])),
    ...field('Added', localTime(r['added_utc'])),
    ...field('Dimensions', dimensions(r)),
    ...field('Favourite', r['favorite'] ? 'yes' : ''),
    ...field('Hidden', r['hidden'] ? 'yes' : ''),
    ...field('Trashed', r['trashed'] ? 'yes' : ''),
    ...field('Location', location(r)),
    ...field('File ID', r['file_id']),
  ];
  private readonly albumDetail: DetailBuilder = (r) => [
    ...field('Title', r['title']),
    ...field('Kind', r['kind']),
    ...field('Items', r['count']),
    ...field('From', localTime(r['start_utc'])),
    ...field('To', localTime(r['end_utc'])),
  ];

  protected readonly columns = computed(() =>
    this.view() === 'photos' ? this.photoColumns : this.albumColumns,
  );
  protected readonly fetch = computed(() =>
    this.view() === 'photos' ? this.fetchPhotos : this.fetchAlbums,
  );
  protected readonly detail = computed(() =>
    this.view() === 'photos' ? this.photoDetail : this.albumDetail,
  );

  /** Only the asset view resolves a thumbnail. */
  protected readonly resolvePreview = computed(() =>
    this.view() === 'photos'
      ? (row: TableRow): Promise<FilePreview | null> =>
          this.analysis.previewFile(String(row['file_id']))
      : null,
  );

  protected readonly title = (r: TableRow): string =>
    String(r['filename'] || r['title'] || 'Photo');
}
