import { Component } from '@angular/core';

@Component({
  selector: 'h1[uiHeading], h2[uiHeading], h3[uiHeading], h4[uiHeading]',
  standalone: true,
  template: `<ng-content />`,
  styleUrl: './heading.component.scss',
  host: { class: 'ui-heading' },
})
export class UiHeadingComponent {}
