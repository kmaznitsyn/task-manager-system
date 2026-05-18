# Frontend — Angular SPA

This folder is intentionally empty. Scaffold it yourself with:

```bash
cd frontend
npx -p @angular/cli@18 ng new taskmanager-ui --routing --style=scss --standalone --skip-git
```

Then install the Keycloak adapter:

```bash
cd taskmanager-ui
npm install keycloak-angular keycloak-js
```

### Environment setup

Create `src/environments/environment.ts`:

```ts
export const environment = {
  production: false,
  keycloak: {
    url: 'http://localhost:8080',
    realm: 'taskmanager',
    clientId: 'taskmanager-web',
  },
  api: {
    userService: 'http://localhost:8001',
    taskService: 'http://localhost:8002',
  },
};
```

See ticket TM-13 for the Keycloak integration, TM-14 for the task list view.
