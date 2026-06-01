import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import {
  DOC_TYPE_LABELS,
  DocType,
  DocumentInput,
} from './document.model';
import { DocumentsService } from './documents.service';
import { ButtonComponent } from '../shared/button/button.component';

const DOC_TYPES: readonly DocType[] = [
  'bill_of_lading',
  'manifest',
  'proof_of_delivery',
  'invoice',
  'customs_declaration',
];

@Component({
  selector: 'app-document-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    ButtonComponent,
  ],
  templateUrl: './document-form.component.html',
  styleUrl: './document-form.component.scss',
})
export class DocumentFormComponent {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private docs = inject(DocumentsService);

  readonly docTypes = DOC_TYPES;
  readonly typeLabels = DOC_TYPE_LABELS;
  readonly state = signal<'idle' | 'saving'>('idle');
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    doc_type: ['bill_of_lading' as DocType, [Validators.required]],
    reference_number: ['', [Validators.required, Validators.maxLength(128)]],
    shipment_ref: ['', [Validators.maxLength(128)]],
    raw_text: ['', [Validators.required]],
  });

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const raw = this.form.getRawValue();
    const shipment = raw.shipment_ref.trim();
    const input: DocumentInput = {
      doc_type: raw.doc_type,
      reference_number: raw.reference_number.trim(),
      shipment_ref: shipment === '' ? null : shipment,
      raw_text: raw.raw_text,
    };

    this.state.set('saving');
    this.error.set(null);
    this.docs.create(input).subscribe({
      next: () => {
        void this.router.navigate(['/documents']);
      },
      error: (err: unknown) => {
        this.error.set(this.describe(err));
        this.state.set('idle');
      },
    });
  }

  private describe(err: unknown): string {
    const e = err as { status?: number; statusText?: string; message?: string };
    if (e?.status === 0) return 'Cannot reach docs service.';
    if (e?.status === 422) return 'The server rejected the form. Check your inputs.';
    if (e?.status) {
      return `Request failed (${e.status} ${e.statusText ?? ''}).`.trim();
    }
    return e?.message ?? 'Unknown error.';
  }
}
