import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { KeycloakService } from 'keycloak-angular';

import { ButtonComponent } from '../shared/button/button.component';
import { UserProfile } from './profile.model';
import { ProfileService } from './profile.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, DatePipe, FormsModule, ButtonComponent],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private profiles = inject(ProfileService);
  private keycloak = inject(KeycloakService);

  readonly state = signal<'loading' | 'loaded' | 'error'>('loading');
  readonly profile = signal<UserProfile | null>(null);

  // Email is read-only and sourced from the Keycloak token (falls back to /me).
  readonly email = signal<string>('');

  readonly editing = signal(false);
  readonly saving = signal(false);
  readonly saveError = signal<string | null>(null);
  readonly justSaved = signal(false);

  draft = '';

  readonly displayName = computed(() => this.profile()?.display_name ?? null);

  readonly initials = computed(() => {
    const name = this.displayName();
    if (name && name.trim()) {
      const parts = name.trim().split(/\s+/);
      const first = parts[0][0];
      const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
      return (first + last).toUpperCase();
    }
    return (this.email()[0] ?? '?').toUpperCase();
  });

  readonly membership = computed(() => {
    const p = this.profile();
    if (!p) return '';
    const created = new Date(p.created_at);
    const now = new Date();
    const months =
      (now.getFullYear() - created.getFullYear()) * 12 +
      (now.getMonth() - created.getMonth());
    if (months < 1) return 'New this month';
    if (months < 12) return `${months} month${months > 1 ? 's' : ''} in`;
    const years = Math.floor(months / 12);
    return `${years} year${years > 1 ? 's' : ''} in`;
  });

  ngOnInit(): void {
    const tokenEmail =
      this.keycloak.getKeycloakInstance()?.tokenParsed?.['email'];
    if (tokenEmail) {
      this.email.set(tokenEmail);
    }
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.profiles.me().subscribe({
      next: (profile) => {
        this.profile.set(profile);
        if (!this.email()) {
          this.email.set(profile.email);
        }
        this.state.set('loaded');
      },
      error: () => this.state.set('error'),
    });
  }

  startEdit(): void {
    this.draft = this.displayName() ?? '';
    this.saveError.set(null);
    this.justSaved.set(false);
    this.editing.set(true);
  }

  cancelEdit(): void {
    this.editing.set(false);
    this.saveError.set(null);
  }

  save(): void {
    const next = this.draft.trim();
    if (next === (this.displayName() ?? '')) {
      this.editing.set(false);
      return;
    }

    this.saving.set(true);
    this.saveError.set(null);
    this.profiles.updateDisplayName(next).subscribe({
      next: (profile) => {
        this.profile.set(profile);
        this.saving.set(false);
        this.editing.set(false);
        this.justSaved.set(true);
        setTimeout(() => this.justSaved.set(false), 2400);
      },
      error: () => {
        this.saving.set(false);
        this.saveError.set('Could not save your display name. Try again.');
      },
    });
  }
}
