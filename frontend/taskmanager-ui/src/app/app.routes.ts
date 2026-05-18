import { Routes } from '@angular/router';
import {AuthGuard} from './auth.guard';
import {LogoutComponent} from './logout/logout.component';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'tasks',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./tasks/task-list.component').then((m) => m.TaskListComponent),
  },
  {
    path: 'tasks/new',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./tasks/task-form.component').then((m) => m.TaskFormComponent),
  },
  {
    path: 'tasks/:id/edit',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./tasks/task-form.component').then((m) => m.TaskFormComponent),
  },
  {
    path: 'logout',
    component: LogoutComponent,
  },
];
