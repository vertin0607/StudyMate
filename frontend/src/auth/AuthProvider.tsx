import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import axios from "axios";

import { loginAccount, logoutAccount, fetchCurrentUser, registerAccount } from "../services/auth.ts";
import type { AuthUser } from "../types/auth.ts";
import { clearCsrf, ensureCsrf, setUnauthorizedHandler } from "../services/api.ts";
import { getErrorMessage } from "../utils/apiError.ts";
import { AuthContext, type AuthContextValue } from "./context.ts";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);
  const bootId = useRef(0);

  const loadSession = useCallback(async (id: number) => {
    try {
      await ensureCsrf(true);
      const current = await fetchCurrentUser();
      if (bootId.current === id) {
        setUser(current);
        setBootError(null);
      }
    } catch (error) {
      if (bootId.current !== id) {
        return;
      }
      setUser(null);
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        setBootError(null);
      } else {
        setBootError(getErrorMessage(error, "暂时无法确认登录状态"));
      }
    } finally {
      if (bootId.current === id) {
        setIsLoading(false);
      }
    }
  }, []);

  const restore = useCallback(async () => {
    const id = bootId.current + 1;
    bootId.current = id;
    setIsLoading(true);
    setBootError(null);
    await loadSession(id);
  }, [loadSession]);

  useEffect(() => {
    const id = bootId.current + 1;
    bootId.current = id;
    void loadSession(id);
  }, [loadSession]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const current = await loginAccount(username, password);
    setUser(current);
    setBootError(null);
  }, []);

  const register = useCallback(async (input: { username: string; password: string; email: string | null }) => {
    await registerAccount(input);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAccount();
    } catch (error) {
      if (!(axios.isAxiosError(error) && error.response?.status === 401)) {
        throw error;
      }
      clearCsrf();
    }
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      bootError,
      login,
      register,
      logout,
      refreshUser: restore,
    }),
    [user, isLoading, bootError, login, register, logout, restore],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
