import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Task, TaskStatus } from './task.model';
import { TasksService } from './tasks.service';
import { ButtonComponent } from '../shared/button/button.component';

type Tab = 'active' | 'deleted';
type StatusFilter = 'all' | TaskStatus;

@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [
    CommonModule,
    DatePipe,
    RouterLink,
    ButtonComponent,
  ],
  templateUrl: './task-list.component.html',
  styleUrl: './task-list.component.scss',
})
export class TaskListComponent implements OnInit {
  private tasks = inject(TasksService);

  readonly state = signal<'loading' | 'loaded' | 'error'>('loading');
  readonly allItems = signal<Task[]>([]);
  readonly error = signal<string | null>(null);
  readonly tab = signal<Tab>('active');
  readonly statusFilter = signal<StatusFilter>('all');

  readonly items = computed(() => {
    const filter = this.statusFilter();
    if (this.tab() === 'deleted' || filter === 'all') return this.allItems();
    return this.allItems().filter(t => t.status === filter);
  });

  ngOnInit(): void {
    this.load();
  }

  switchTab(t: Tab): void {
    if (this.tab() === t) return;
    this.tab.set(t);
    this.statusFilter.set('all');
    this.load();
  }

  setFilter(f: StatusFilter): void {
    this.statusFilter.set(f);
  }

  load(): void {
    this.state.set('loading');
    this.error.set(null);
    const source = this.tab() === 'deleted'
      ? this.tasks.listDeleted()
      : this.tasks.list();
    source.subscribe({
      next: (rows) => {
        this.allItems.set(rows);
        this.state.set('loaded');
      },
      error: (err: unknown) => {
        this.error.set(this.describe(err));
        this.state.set('error');
      },
    });
  }

  deleteTask(id: string): void {
    if (!confirm('Are you sure you want to delete this task?')) return;
    this.tasks.delete(id).subscribe({
      next: () => this.allItems.update(items => items.filter(t => t.id !== id)),
      error: (err: unknown) => alert(this.describe(err)),
    });
  }

  restoreTask(id: string): void {
    this.tasks.restore(id).subscribe({
      next: () => this.allItems.update(items => items.filter(t => t.id !== id)),
      error: (err: unknown) => alert(this.describe(err)),
    });
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
