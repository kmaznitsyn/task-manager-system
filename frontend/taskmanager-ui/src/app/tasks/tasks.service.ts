import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Task, TaskInput } from './task.model';

@Injectable({ providedIn: 'root' })
export class TasksService {
  private http = inject(HttpClient);
  private base = environment.api.taskService;

  list(): Observable<Task[]> {
    return this.http.get<Task[]>(`${this.base}/tasks`);
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
}
