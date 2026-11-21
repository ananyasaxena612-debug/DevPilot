/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";
import {
  getCurrentUser,
  loginUser,
  registerUser,
  logoutUser as apiLogout,
  getStoredToken,
} from "../services/api";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => getStoredToken());
  const [loading, setLoading] = useState(true);

  // Load user profile on initial mount or token change
  useEffect(() => {
    let isMounted = true;

    async function checkAuth() {
      const stored = getStoredToken();
      if (!stored) {
        if (isMounted) {
          setUser(null);
          setLoading(false);
        }
        return;
      }

      try {
        const res = await getCurrentUser();
        if (isMounted && res?.user) {
          setUser(res.user);
        }
      } catch {
        // Token might be invalid or backend offline, clear user
        if (isMounted) {
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    checkAuth();
    return () => {
      isMounted = false;
    };
  }, [token]);

  const login = async (email, password) => {
    const res = await loginUser(email, password);
    if (res?.token && res?.user) {
      setToken(res.token);
      setUser(res.user);
    }
    return res;
  };

  const register = async (email, password, name) => {
    const res = await registerUser(email, password, name);
    if (res?.token && res?.user) {
      setToken(res.token);
      setUser(res.user);
    }
    return res;
  };

  const logout = () => {
    apiLogout();
    setToken("");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

