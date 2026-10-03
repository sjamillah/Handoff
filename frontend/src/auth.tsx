import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, UNAUTHORIZED, type User } from "./api";

interface Auth {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<Auth | null>(null);

/** Holds the signed-in user: asks the server on load and forgets the user on any 401. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me().then(setUser, () => setUser(null)).finally(() => setLoading(false));
    const forget = () => setUser(null);
    window.addEventListener(UNAUTHORIZED, forget);
    return () => window.removeEventListener(UNAUTHORIZED, forget);
  }, []);

  const signIn = async (email: string, password: string) => setUser(await api.login(email, password));
  const signOut = async () => {
    await api.logout().catch(() => null);
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, signIn, signOut }}>{children}</AuthContext.Provider>;
}

/** The current auth state. */
export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used inside AuthProvider");
  return auth;
}
