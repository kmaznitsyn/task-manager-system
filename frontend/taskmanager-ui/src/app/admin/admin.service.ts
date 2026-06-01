import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { UsersPage } from './keycloak-user.model';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private http = inject(HttpClient);
  private base = environment.api.userService;

  listUsers(first: number, max: number, search: string): Observable<UsersPage> {
    let params = new HttpParams().set('first', first).set('max', max);
    const q = search.trim();
    if (q) params = params.set('search', q);
    return this.http.get<UsersPage>(`${this.base}/admin/users`, { params });
  }

  deleteUser(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/admin/users/${id}`);
  }
}
