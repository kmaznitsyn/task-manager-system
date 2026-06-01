import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ButtonComponent } from '../shared/button/button.component';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, ButtonComponent],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {}
