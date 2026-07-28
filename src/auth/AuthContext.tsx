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
  applyProfile: (profile: UserProfile) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(api.isDemoMode ? "anonymous" : "loading");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  /*
   * Считает смены сеанса. Без него вход под другим аккаунтом не менял
   * status — он уже был "authenticated" — и кабинет продолжал
   * здороваться именем предыдущего пользователя.
   */
  const [session, setSession] = useState(0);

  useEffect(() => {
    if (api.isDemoMode) return;

    let cancelled = false;
    api.refreshSession()
      .then((tokens) => {
        if (cancelled) return;
        setAccessToken(tokens.accessToken);
        setStatus("authenticated");
        setSession((current) => current + 1);
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
      setSession((current) => current + 1);
    });

    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const tokens = await api.login(payload);
    setAccessToken(tokens.accessToken);
    setProfile(null);
    setStatus("authenticated");
    setSession((current) => current + 1);
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const tokens = await api.register(payload);
    setAccessToken(tokens.accessToken);
    setProfile(null);
    setStatus("authenticated");
    setSession((current) => current + 1);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearAccessToken();
      setProfile(null);
      setStatus("anonymous");
      setSession((current) => current + 1);
    }
  }, []);

  useEffect(() => {
    // В демо-режиме входа нет, но профиль всё равно нужен: иначе
    // страница профиля осталась бы на бесконечной загрузке.
    if (status !== "authenticated" && !api.isDemoMode) return;

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
  }, [status, session]);

  const applyProfile = useCallback((updated: UserProfile) => {
    setProfile(updated);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, profile, login, register, logout, applyProfile }),
    [status, profile, login, register, logout, applyProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
