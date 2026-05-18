import { Component, OnInit } from '@angular/core';

import { KeycloakService } from 'keycloak-angular';

@Component({
  selector: 'app-logout',
  standalone: true,
  template: `
    <div class="logout">
      <div class="spinner" aria-hidden="true"></div>
      <p>Logging out…</p>
    </div>
  `,
  styleUrls: ['./logout.component.scss'],
})
export class LogoutComponent implements OnInit {
  constructor(private keycloak: KeycloakService) {}

  async ngOnInit() {
    await this.keycloak.logout(window.location.origin);
  }
}
