import { CommonModule, DatePipe, KeyValuePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import {
  DOC_TYPE_LABELS,
  DocStatus,
  LogisticsDocument,
} from './document.model';
import { DocumentsService } from './documents.service';
import { ButtonComponent } from '../shared/button/button.component';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [
    CommonModule,
    DatePipe,
    KeyValuePipe,
    RouterLink,
    ButtonComponent,
  ],
  templateUrl: './document-list.component.html',
  styleUrl: './document-list.component.scss',
})
export class DocumentListComponent implements OnInit {
  private docs = inject(DocumentsService);

  readonly typeLabels = DOC_TYPE_LABELS;
  readonly state = signal<'loading' | 'loaded' | 'error'>('loading');
  readonly items = signal<LogisticsDocument[]>([]);
  readonly error = signal<string | null>(null);
  readonly busyId = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.error.set(null);
    this.docs.list().subscribe({
      next: (rows) => {
        this.items.set(rows);
        this.state.set('loaded');
      },
      error: (err: unknown) => {
        this.error.set(this.describe(err));
        this.state.set('error');
      },
    });
  }

  process(d: LogisticsDocument): void {
    this.busyId.set(d.id);
    this.docs.process(d.id).subscribe({
      next: (updated) => {
        this.items.update((rows) =>
          rows.map((r) => (r.id === updated.id ? updated : r)),
        );
        this.busyId.set(null);
      },
      error: () => this.busyId.set(null),
    });
  }

  remove(d: LogisticsDocument): void {
    if (!confirm(`Delete document "${d.reference_number}"?`)) return;
    this.busyId.set(d.id);
    this.docs.delete(d.id).subscribe({
      next: () => {
        this.items.update((rows) => rows.filter((r) => r.id !== d.id));
        this.busyId.set(null);
      },
      error: () => this.busyId.set(null),
    });
  }

  private describe(err: unknown): string {
    const e = err as { status?: number; statusText?: string; message?: string };
    if (e?.status === 0) return 'Cannot reach docs service.';
    if (e?.status) {
      return `Request failed (${e.status} ${e.statusText ?? ''}).`.trim();
    }
    return e?.message ?? 'Unknown error loading documents.';
  }
}
