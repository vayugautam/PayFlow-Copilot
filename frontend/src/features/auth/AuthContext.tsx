import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { api, TOKEN_KEY } from "../../lib/api";
import type { TokenResponse, User } from "../../types/api";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY));
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await api.get<User>("/auth/me")).data,
    enabled: Boolean(token),
  });

  useEffect(() => {
    const unauthorized = () => {
      sessionStorage.removeItem(TOKEN_KEY);
      setToken(null);
      queryClient.removeQueries({ queryKey: ["auth", "me"] });
    };
    window.addEventListener("payflow:unauthorized", unauthorized);
    return () => window.removeEventListener("payflow:unauthorized", unauthorized);
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user: query.data ?? null,
    isLoading: Boolean(token) && query.isLoading,
    login: async (email, password) => {
      const { data } = await api.post<TokenResponse>("/auth/login", { email, password });
      sessionStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      await query.refetch();
    },
    register: async (email, password) => {
      await api.post("/auth/register", { email, password });
    },
    logout: () => {
      sessionStorage.removeItem(TOKEN_KEY);
      setToken(null);
      queryClient.removeQueries({ queryKey: ["auth", "me"] });
    },
  }), [query.data, query.isLoading, query.refetch, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}

import { queryClient } from "../../lib/query-client";
