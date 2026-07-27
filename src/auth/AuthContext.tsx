import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setUnauthorizedHandler } from "../api/client";
import type {
  LoginPayload,
  RegisterPayload,
  UserProfile,
} from "../api/contracts";
import { clearAccessToken, setAccessToken } from "./tokenStore";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

type AuthContextValue = {
  status: AuthStatus;
  profile: UserProfile | null;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(api.isDemoMode ? "anonymous" : "loading");
  const [profile, setProfile] = useState<UserProfile | null>(null);

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

  useEffect(() => {
    // Любой 401, который не удалось починить обновлением токена,
    // означает окончившийся сеанс: интерфейс должен предложить войти,
    // а не показывать карточку ошибки на каждом экране.
    setUnauthorizedHandler(() => {
      clearAccessToken();
      setProfile(null);
      setStatus("anonymous");
    });

    return () => setUnauthorizedHandler(null);
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
      setProfile(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    if (status !== "authenticated") return;

    let cancelled = false;
    api.getProfile()
      .then((loaded) => {
        if (!cancelled) setProfile(loaded);
      })
      .catch(() => {
        // Имя — украшение: без него кабинет работает, просто здоровается
        // нейтрально.
        if (!cancelled) setProfile(null);
      });

    return () => {
      cancelled = true;
    };
  }, [status]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, profile, login, register, logout }),
    [status, profile, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
