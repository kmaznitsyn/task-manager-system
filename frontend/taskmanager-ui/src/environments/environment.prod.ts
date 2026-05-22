export const environment = {
  production: true,

  keycloak: {
    url: 'https://keycloak-d57bj7qdsa-ey.a.run.app',
    realm: 'taskmanager',
    clientId: 'taskmanager-web',
  },

  api: {
    userService: 'https://user-service-d57bj7qdsa-ey.a.run.app',
    taskService: 'https://task-service-d57bj7qdsa-ey.a.run.app',
  },
};
