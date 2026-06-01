import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { UserProfile } from './profile.model';

@Injectable({ providedIn: 'root' })
export class ProfileService {
  private http = inject(HttpClient);
  private base = environment.api.userService;

  me(): Observable<UserProfile> {
    return this.http.get<UserProfile>(`${this.base}/me`);
  }

  updateDisplayName(displayName: string): Observable<UserProfile> {
    return this.http.patch<UserProfile>(`${this.base}/me`, {
      display_name: displayName,
    });
  }
}
