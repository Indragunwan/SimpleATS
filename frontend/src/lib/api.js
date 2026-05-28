import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("cvs_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("cvs_token");
      localStorage.removeItem("cvs_user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export default api;

export const ROLE_LABELS = {
  hr_recruiter: "HR Recruiter",
  hiring_manager: "Hiring Manager",
  admin_it: "Admin IT",
};

export const SCORE_BAND = (score) => {
  if (score >= 75) return "high";
  if (score >= 40) return "mid";
  return "low";
};

export const BAND_COLORS = {
  high: "text-emerald-700 bg-emerald-50 border-emerald-200",
  mid: "text-amber-700 bg-amber-50 border-amber-200",
  low: "text-rose-700 bg-rose-50 border-rose-200",
};

export const RECOMMENDATION_LABELS = {
  shortlist: "Daftar Pendek",
  review: "Tinjau Lanjut",
  reject: "Tidak Sesuai",
  pending: "Memproses",
};

export const DECISION_LABELS = {
  pending: "Belum Diputuskan",
  shortlisted: "Di-shortlist",
  rejected: "Ditolak",
  hold: "Ditahan",
};
