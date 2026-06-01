import { environment } from '../environments/environment';

export function isInternalApi(url: string): boolean {
  return [
    environment.api.userService,
    environment.api.taskService,
    environment.api.docsService,
  ].some((api) => url.startsWith(api));
}
