import {
  HttpInterceptorFn,
} from '@angular/common/http';

import { inject } from '@angular/core';

import { KeycloakService } from 'keycloak-angular';
import {isInternalApi} from './api.utils';
import {from, switchMap} from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (
  req,
  next
) => {
  if (!isInternalApi) {
    return next(req);
  }

  const keycloak = inject(KeycloakService);

  return from(keycloak.getToken()).pipe(
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
    })
  );
};
