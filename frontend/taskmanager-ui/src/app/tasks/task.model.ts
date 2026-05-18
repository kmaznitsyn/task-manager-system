export type TaskStatus = 'todo' | 'doing' | 'done';

export interface Task {
  id: string;
  owner_sub: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  due_date: string | null; // ISO date (YYYY-MM-DD) or null
  created_at: string;
  updated_at: string;
}

export interface TaskInput {
  title: string;
  description: string | null;
  status: TaskStatus;
  due_date: string | null;
}
