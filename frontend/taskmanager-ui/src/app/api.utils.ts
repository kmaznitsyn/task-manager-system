import { environment } from '../environments/environment';

export function isInternalApi(url: string): boolean {
  return [
    environment.api.userService,
    environment.api.taskService,
  ].some((api) => url.startsWith(api));
}
