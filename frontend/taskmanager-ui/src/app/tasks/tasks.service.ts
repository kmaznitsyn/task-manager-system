import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Label, Task, TaskInput } from './task.model';

@Injectable({ providedIn: 'root' })
export class TasksService {
  private http = inject(HttpClient);
  private base = environment.api.taskService;

  list(status?: string): Observable<Task[]> {
    const url = `${this.base}/tasks`;
    if (status) {
      return this.http.get<Task[]>(url, { params: { status } });
    }
    return this.http.get<Task[]>(url);
  }

  listDeleted(): Observable<Task[]> {
    return this.http.get<Task[]>(`${this.base}/tasks/deleted`);
  }

  get(id: string): Observable<Task> {
    return this.http.get<Task>(`${this.base}/tasks/${id}`);
  }

  create(input: TaskInput): Observable<Task> {
    return this.http.post<Task>(`${this.base}/tasks`, input);
  }

  update(id: string, input: TaskInput): Observable<Task> {
    return this.http.patch<Task>(`${this.base}/tasks/${id}`, input);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/tasks/${id}`);
  }

  restore(id: string): Observable<Task> {
    return this.http.post<Task>(`${this.base}/tasks/${id}/restore`, {});
  }

  labels(): Observable<Label[]> {
    return this.http.get<Label[]>(`${this.base}/labels`);
  }
}
