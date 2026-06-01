export interface KeycloakUser {
  id: string;
  username: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  enabled: boolean;
  created_timestamp: number | null;
}

export interface UsersPage {
  users: KeycloakUser[];
  total: number;
  first: number;
  max: number;
}
