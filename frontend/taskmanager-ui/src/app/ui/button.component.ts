import { Component, Input } from '@angular/core';

export type UiButtonVariant = 'primary' | 'ghost' | 'danger';

@Component({
  selector: 'button[uiButton]',
  standalone: true,
  template: `<ng-content />`,
  styleUrl: './button.component.scss',
  host: {
    class: 'ui-button',
    '[attr.data-variant]': 'variant',
  },
})
export class UiButtonComponent {
  @Input() variant: UiButtonVariant = 'primary';
}
