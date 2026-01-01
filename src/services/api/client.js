import axios from "axios";
import { useAuthStore } from "../../store/auth.store.js";
import { endpoints } from "./endpoints.js";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshing = false;
let queued = [];

function queueRequest(cb) {
  queued.push(cb);
}
function flushQueue(newToken) {
  queued.forEach((cb) => cb(newToken));
  queued = [];
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error?.response?.status;

    // If not 401 or already retried, reject
    if (status !== 401 || original?._retry) {
      return Promise.reject(error);
    }

    const store = useAuthStore.getState();
    if (!store.refreshToken) {
      store.logout();
      return Promise.reject(error);
    }

    // Mark as retried
    original._retry = true;

    // If refresh already in progress, wait
    if (refreshing) {
      return new Promise((resolve, reject) => {
        queueRequest((newToken) => {
          if (!newToken) return reject(error);
          original.headers.Authorization = `Bearer ${newToken}`;
          resolve(api(original));
        });
      });
    }

    refreshing = true;
    try {
      const resp = await axios.post(
        `${import.meta.env.VITE_API_URL}${endpoints.auth.refresh}`,
        { refresh: store.refreshToken }
      );

      const newAccess = resp?.data?.access;
      if (!newAccess) throw new Error("No access token from refresh.");

      store.setAccessToken(newAccess);
      flushQueue(newAccess);

      original.headers.Authorization = `Bearer ${newAccess}`;
      return api(original);
    } catch (e) {
      flushQueue(null);
      store.logout();
      return Promise.reject(e);
    } finally {
      refreshing = false;
    }
  }
);

export { api };
