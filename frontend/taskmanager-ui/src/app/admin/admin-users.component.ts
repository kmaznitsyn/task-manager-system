import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { KeycloakService } from 'keycloak-angular';

import { ButtonComponent } from '../shared/button/button.component';
import { AdminService } from './admin.service';
import { KeycloakUser } from './keycloak-user.model';

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonComponent],
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.scss',
})
export class AdminUsersComponent implements OnInit {
  private admin = inject(AdminService);
  private keycloak = inject(KeycloakService);

  readonly pageSize = 10;

  readonly state = signal<'loading' | 'loaded' | 'error'>('loading');
  readonly users = signal<KeycloakUser[]>([]);
  readonly total = signal(0);
  readonly first = signal(0);
  readonly search = signal('');
  readonly error = signal<string | null>(null);
  readonly busyId = signal<string | null>(null);

  readonly selfSub = this.keycloak.getKeycloakInstance().subject ?? '';

  readonly page = computed(() => Math.floor(this.first() / this.pageSize) + 1);
  readonly pageCount = computed(() =>
    Math.max(1, Math.ceil(this.total() / this.pageSize)),
  );
  readonly rangeStart = computed(() =>
    this.total() === 0 ? 0 : this.first() + 1,
  );
  readonly rangeEnd = computed(() =>
    Math.min(this.first() + this.pageSize, this.total()),
  );

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.error.set(null);
    this.admin.listUsers(this.first(), this.pageSize, this.search()).subscribe({
      next: (page) => {
        this.users.set(page.users);
        this.total.set(page.total);
        this.state.set('loaded');
      },
      error: (err: unknown) => {
        this.error.set(this.describe(err));
        this.state.set('error');
      },
    });
  }

  applySearch(): void {
    this.first.set(0);
    this.load();
  }

  clearSearch(): void {
    if (!this.search()) return;
    this.search.set('');
    this.first.set(0);
    this.load();
  }

  prev(): void {
    if (this.first() === 0) return;
    this.first.set(Math.max(0, this.first() - this.pageSize));
    this.load();
  }

  next(): void {
    if (this.first() + this.pageSize >= this.total()) return;
    this.first.set(this.first() + this.pageSize);
    this.load();
  }

  remove(u: KeycloakUser): void {
    if (u.id === this.selfSub) return;
    const label = u.username || u.email || u.id;
    if (
      !confirm(
        `Permanently delete user "${label}" from Keycloak? This cannot be undone.`,
      )
    )
      return;
    this.busyId.set(u.id);
    this.admin.deleteUser(u.id).subscribe({
      next: () => {
        this.busyId.set(null);
        // Stepping back a page if we just emptied the last one.
        if (this.users().length === 1 && this.first() > 0) {
          this.first.set(Math.max(0, this.first() - this.pageSize));
        }
        this.load();
      },
      error: (err: unknown) => {
        this.busyId.set(null);
        this.error.set(this.describe(err));
      },
    });
  }

  fullName(u: KeycloakUser): string {
    const name = [u.first_name, u.last_name].filter(Boolean).join(' ');
    return name || u.username;
  }

  initials(u: KeycloakUser): string {
    const a = (u.first_name || u.username || '?').trim();
    const b = (u.last_name || '').trim();
    return ((a[0] ?? '?') + (b[0] ?? '')).toUpperCase();
  }

  avatarHue(id: string): number {
    let hash = 0;
    for (let i = 0; i < id.length; i++) {
      hash = (hash * 31 + id.charCodeAt(i)) % 360;
    }
    return hash;
  }

  private describe(err: unknown): string {
    const e = err as {
      status?: number;
      statusText?: string;
      error?: { detail?: string };
    };
    if (e?.status === 0) return 'Cannot reach user service.';
    if (e?.status === 403) return 'You do not have permission to manage users.';
    if (e?.status === 502) return e?.error?.detail ?? 'Keycloak is unreachable.';
    if (e?.status) {
      return `Request failed (${e.status} ${e.statusText ?? ''}).`.trim();
    }
    return 'Unknown error loading users.';
  }
}
