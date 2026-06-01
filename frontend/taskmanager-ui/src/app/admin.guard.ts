import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';

import { KeycloakService } from 'keycloak-angular';

@Injectable({
  providedIn: 'root',
})
export class AdminGuard implements CanActivate {
  constructor(
    private readonly keycloak: KeycloakService,
    private readonly router: Router,
  ) {}

  canActivate(): boolean {
    if (this.keycloak.isLoggedIn() && this.keycloak.isUserInRole('admin')) {
      return true;
    }
    this.router.navigate(['/']);
    return false;
  }
}
