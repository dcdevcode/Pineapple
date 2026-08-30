import { Component, input } from '@angular/core';

/** How big the lockup renders. `large` is for hero use (the About tab). */
export type BrandSize = 'compact' | 'large';

/**
 * The Pineapple brand lockup — the full `logo.png` (pineapple mark + wordmark)
 * as one image. Reused wherever the app names itself: the shell's top-left
 * corner (`compact`, the default) and the About tab (`large`).
 */
@Component({
  selector: 'app-brand',
  templateUrl: './brand.html',
  styleUrl: './brand.scss',
  host: { class: 'brand', '[class.brand--large]': "size() === 'large'" },
})
export class Brand {
  readonly size = input<BrandSize>('compact');
}
