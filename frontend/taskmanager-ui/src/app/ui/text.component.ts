import { Component, Input } from '@angular/core';

export type UiTextVariant = 'default' | 'muted' | 'error' | 'loading';

@Component({
  selector: 'p[uiText], span[uiText]',
  standalone: true,
  template: `<ng-content />`,
  styleUrl: './text.component.scss',
  host: {
    class: 'ui-text',
    '[attr.data-variant]': 'variant',
  },
})
export class UiTextComponent {
  @Input() variant: UiTextVariant = 'default';
}
