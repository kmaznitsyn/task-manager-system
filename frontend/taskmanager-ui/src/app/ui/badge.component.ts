import { Component, Input } from '@angular/core';

export type UiBadgeTone = 'neutral' | 'info' | 'warning' | 'success' | 'danger';

@Component({
  selector: 'span[uiBadge]',
  standalone: true,
  template: `<ng-content />`,
  styleUrl: './badge.component.scss',
  host: {
    class: 'ui-badge',
    '[attr.data-tone]': 'tone',
  },
})
export class UiBadgeComponent {
  @Input() tone: UiBadgeTone = 'neutral';
}
