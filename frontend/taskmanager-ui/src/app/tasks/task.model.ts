export type TaskStatus = 'todo' | 'doing' | 'done';

export interface Label {
  id: string;
  owner_sub: string;
  name: string;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  owner_sub: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  due_date: string | null; // ISO date (YYYY-MM-DD) or null
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  labels: Label[];
}

export interface TaskInput {
  title: string;
  description: string | null;
  status: TaskStatus;
  due_date: string | null;
  labels: string[]; // label names; the backend resolves/creates them
}
