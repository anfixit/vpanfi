import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type { LoginPayload, RegisterPayload } from "../api/contracts";
import { clearAccessToken, setAccessToken } from "./tokenStore";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

type AuthContextValue = {
  status: AuthStatus;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(api.isDemoMode ? "anonymous" : "loading");

  useEffect(() => {
    if (api.isDemoMode) return;

    let cancelled = false;
    api.refreshSession()
      .then((tokens) => {
        if (cancelled) return;
        setAccessToken(tokens.accessToken);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        clearAccessToken();
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const tokens = await api.login(payload);
    setAccessToken(tokens.accessToken);
    setStatus("authenticated");
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const tokens = await api.register(payload);
    setAccessToken(tokens.accessToken);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearAccessToken();
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, login, register, logout }),
    [status, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
