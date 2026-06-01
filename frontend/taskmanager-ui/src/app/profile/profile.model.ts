export interface UserProfile {
  id: string;
  keycloak_sub: string;
  email: string;
  display_name: string | null;
  created_at: string;
  updated_at: string;
}
