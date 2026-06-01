import {
  HttpInterceptorFn,
  HttpErrorResponse,
} from '@angular/common/http';

import { inject } from '@angular/core';

import { KeycloakService } from 'keycloak-angular';
import { isInternalApi } from './api.utils';
import { from, switchMap, catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (
  req,
  next
) => {
  if (!isInternalApi(req.url)) {
    return next(req);
  }

  const keycloak = inject(KeycloakService);

  return from(keycloak.updateToken(30)).pipe(
    switchMap(() => keycloak.getToken()),
    switchMap((token) => {
      if (!token) {
        return next(req);
      }

      const cloned = req.clone({
        setHeaders: {
          Authorization: `Bearer ${token}`,
        },
      });

      return next(cloned);
    }),
    catchError((err) => {
      if (err instanceof HttpErrorResponse && err.status === 401) {
        keycloak.login({ redirectUri: window.location.href });
      }
      return throwError(() => err);
    })
  );
};
