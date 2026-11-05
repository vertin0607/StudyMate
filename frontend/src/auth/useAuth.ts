import { useContext } from "react";

import { AuthContext } from "./context.ts";

export function useAuth() {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth 必须放在 AuthProvider 中");
  }
  return value;
}
