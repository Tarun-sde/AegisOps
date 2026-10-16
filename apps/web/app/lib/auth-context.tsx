"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { getMe, logoutUser, type AuthResponse } from "./api";

interface AuthContextValue {
  user: AuthResponse["user"] | null;
  activeOrg: AuthResponse["active_organization"] | null;
  role: string | null;
  organizations: AuthResponse["organizations"];
  isAuthenticated: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  activeOrg: null,
  role: null,
  organizations: [],
  isAuthenticated: false,
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthResponse["user"] | null>(null);
  const [activeOrg, setActiveOrg] = useState<
    AuthResponse["active_organization"] | null
  >(null);
  const [role, setRole] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<
    AuthResponse["organizations"]
  >([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data, error } = await getMe();
      if (!error && data) {
        setUser(data.user);
        setActiveOrg(data.active_organization);
        setRole(data.role);
        setOrganizations(data.organizations || []);
      } else {
        setUser(null);
        setActiveOrg(null);
        setRole(null);
        setOrganizations([]);
      }
    } catch {
      setUser(null);
      setActiveOrg(null);
      setRole(null);
      setOrganizations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    const result = await logoutUser();
    if (result.error) throw new Error(result.error);
    setUser(null);
    setActiveOrg(null);
    setRole(null);
    setOrganizations([]);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider
      value={{
        user,
        activeOrg,
        role,
        organizations,
        isAuthenticated: !!user,
        loading,
        refresh,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
