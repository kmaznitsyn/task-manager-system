import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Task, TaskStatus } from './task.model';
import { TasksService } from './tasks.service';
import {
  UiBadgeComponent,
  UiBadgeTone,
  UiButtonComponent,
  UiHeadingComponent,
  UiTextComponent,
} from '../ui';

const STATUS_TONE: Record<TaskStatus, UiBadgeTone> = {
  todo: 'neutral',
  doing: 'warning',
  done: 'success',
};

@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [
    CommonModule,
    DatePipe,
    RouterLink,
    UiBadgeComponent,
    UiButtonComponent,
    UiHeadingComponent,
    UiTextComponent,
  ],
  templateUrl: './task-list.component.html',
  styleUrl: './task-list.component.scss',
})
export class TaskListComponent implements OnInit {
  private tasks = inject(TasksService);

  readonly state = signal<'loading' | 'loaded' | 'error'>('loading');
  readonly items = signal<Task[]>([]);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.error.set(null);
    this.tasks.list().subscribe({
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

  toneFor(status: TaskStatus): UiBadgeTone {
    return STATUS_TONE[status];
  }

  private describe(err: unknown): string {
    const e = err as { status?: number; statusText?: string; message?: string };
    if (e?.status === 0) return 'Cannot reach task service.';
    if (e?.status) {
      return `Request failed (${e.status} ${e.statusText ?? ''}).`.trim();
    }
    return e?.message ?? 'Unknown error loading tasks.';
  }
}
