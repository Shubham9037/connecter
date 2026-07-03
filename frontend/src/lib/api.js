import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Shared axios instance — sends the session cookie on every request.
export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});
