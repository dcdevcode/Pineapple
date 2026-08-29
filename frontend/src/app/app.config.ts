import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ThemeService } from './settings/theme.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideNoopAnimations(),
    provideAppInitializer(() => inject(ThemeService).init()),
  ],
};
