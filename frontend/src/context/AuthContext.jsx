import { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem("cvs_user");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("cvs_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((r) => {
        setUser(r.data);
        localStorage.setItem("cvs_user", JSON.stringify(r.data));
      })
      .catch(() => {
        localStorage.removeItem("cvs_token");
        localStorage.removeItem("cvs_user");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email) => {
    const { data } = await api.post("/auth/login", { email });
    localStorage.setItem("cvs_token", data.access_token);
    localStorage.setItem("cvs_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const loginWithGoogle = async (credential) => {
    const { data } = await api.post("/auth/google-login", { credential });
    localStorage.setItem("cvs_token", data.access_token);
    localStorage.setItem("cvs_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("cvs_token");
    localStorage.removeItem("cvs_user");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
