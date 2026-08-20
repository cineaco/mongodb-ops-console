import { createContext, useContext } from "react";
import type { UserMe } from "../api/auth";

export interface AuthContextType { user: UserMe | null; setUser: (user: UserMe | null) => void; }
export const AuthContext = createContext<AuthContextType>({ user: null, setUser: () => {} });
export function useAuth() { return useContext(AuthContext); }
