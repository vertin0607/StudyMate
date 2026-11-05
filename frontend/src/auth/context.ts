import { createContext } from "react";

import type { AuthUser } from "../types/auth.ts";

export type AuthContextValue = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  bootError: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (input: { username: string; password: string; email: string | null }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
