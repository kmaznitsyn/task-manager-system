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
