export const endpoints = {
  auth: {
    login: "/api/auth/login/",
    register: "/api/auth/register/",
    me: "/api/auth/me/",
    refresh: "/api/auth/refresh/",
    socialStart: (provider) => `/api/auth/social/${provider}/start/`,
  },
  catalog: {
    products: "/api/products/",
    categories: "/api/categories/",
    productBySlug: (slug) => `/api/products/${slug}/`,
  },
  quote: {
    create: "/api/quote/",
    recommend: "/api/quote/recommend/",
    save: "/api/quote/save/",
    saved: "/api/quote/saved/",
  },
  orders: {
    myOrders: "/api/orders/me/",
    orderById: (id) => `/api/orders/${id}/`,
    createManual: "/api/orders/create-manual/",
    updateStatus: (id) => `/api/orders/${id}/status/`,
  },
};
