import { Routes } from '@angular/router';
import {AuthGuard} from './auth.guard';
import {AdminGuard} from './admin.guard';
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
    path: 'documents',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./documents/document-list.component').then(
        (m) => m.DocumentListComponent,
      ),
  },
  {
    path: 'documents/new',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./documents/document-form.component').then(
        (m) => m.DocumentFormComponent,
      ),
  },
  {
    path: 'profile',
    canActivate: [AuthGuard],
    loadComponent: () =>
      import('./profile/profile.component').then((m) => m.ProfileComponent),
  },
  {
    path: 'admin',
    canActivate: [AuthGuard, AdminGuard],
    loadComponent: () =>
      import('./admin/admin-users.component').then(
        (m) => m.AdminUsersComponent,
      ),
  },
  {
    path: 'logout',
    component: LogoutComponent,
  },
];
