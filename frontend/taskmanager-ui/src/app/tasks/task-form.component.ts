import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { TaskInput, TaskStatus } from './task.model';
import { TasksService } from './tasks.service';
import { UiButtonComponent, UiHeadingComponent, UiTextComponent } from '../ui';

const STATUSES: readonly TaskStatus[] = ['todo', 'doing', 'done'];

function notBlank(control: AbstractControl): ValidationErrors | null {
  const v = control.value;
  if (typeof v === 'string' && v.trim() === '') {
    return { blank: true };
  }
  return null;
}

@Component({
  selector: 'app-task-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    UiButtonComponent,
    UiHeadingComponent,
    UiTextComponent,
  ],
  templateUrl: './task-form.component.html',
  styleUrl: './task-form.component.scss',
})
export class TaskFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private tasks = inject(TasksService);

  readonly statuses = STATUSES;
  readonly id = signal<string | null>(null);
  readonly mode = computed<'create' | 'edit'>(() =>
    this.id() ? 'edit' : 'create',
  );
  readonly state = signal<'idle' | 'loading' | 'saving' | 'load-error'>('idle');
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200), notBlank]],
    description: ['', [Validators.maxLength(2000)]],
    status: ['todo' as TaskStatus, [Validators.required]],
    due_date: [''],
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.id.set(id);
      this.load(id);
    }
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const raw = this.form.getRawValue();
    const description = raw.description.trim();
    const input: TaskInput = {
      title: raw.title.trim(),
      description: description === '' ? null : description,
      status: raw.status,
      due_date: raw.due_date === '' ? null : raw.due_date,
    };

    this.state.set('saving');
    this.error.set(null);

    const id = this.id();
    const req$ = id ? this.tasks.update(id, input) : this.tasks.create(input);
    req$.subscribe({
      next: () => {
        void this.router.navigate(['/tasks']);
      },
      error: (err: unknown) => {
        this.error.set(this.describe(err));
        this.state.set('idle');
      },
    });
  }

  private load(id: string): void {
    this.state.set('loading');
    this.error.set(null);
    this.tasks.get(id).subscribe({
      next: (t) => {
        this.form.setValue({
          title: t.title,
          description: t.description ?? '',
          status: t.status,
          due_date: t.due_date ?? '',
        });
        this.state.set('idle');
      },
      error: (err: unknown) => {
        this.error.set(this.describe(err));
        this.state.set('load-error');
      },
    });
  }

  private describe(err: unknown): string {
    const e = err as { status?: number; statusText?: string; message?: string };
    if (e?.status === 0) return 'Cannot reach task service.';
    if (e?.status === 404) return 'Task not found.';
    if (e?.status === 400) return 'The server rejected the form. Check your inputs.';
    if (e?.status) {
      return `Request failed (${e.status} ${e.statusText ?? ''}).`.trim();
    }
    return e?.message ?? 'Unknown error.';
  }
}
