import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { KeycloakService } from 'keycloak-angular';

import { ButtonComponent } from './shared/button/button.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ButtonComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  title = 'taskmanager-ui';
  readonly isAdmin = inject(KeycloakService).isUserInRole('admin');
}
