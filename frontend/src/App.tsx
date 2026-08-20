import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "./hooks/useAuth";
import { fetchMe, type UserMe } from "./api/auth";
import LoginPage from "./pages/LoginPage";
import Layout from "./components/Layout";
import RequireRole from "./components/RequireRole";
import ClustersPage from "./pages/ClustersPage";
import UsersPage from "./pages/UsersPage";
import SecretsPage from "./pages/SecretsPage";
import AuditPage from "./pages/AuditPage";
import AccountPage from "./pages/AccountPage";
import AlertsPage from "./pages/AlertsPage";
import ClusterDetailPage from "./pages/ClusterDetailPage";
import ClusterNewPage from "./pages/ClusterNewPage";

const queryClient = new QueryClient();

export default function App() {
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem("refresh_token")));

  useEffect(() => {
    const refresh = localStorage.getItem("refresh_token");
    if (refresh) {
      fetchMe()
        .then(setUser)
        .catch(() => setUser(null))
        .finally(() => setLoading(false));
    }
  }, []);

  if (loading)
    return (
      <div className="flex h-screen items-center justify-center">
        Loading...
      </div>
    );

  return (
    <AuthContext.Provider value={{ user, setUser }}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={user ? <Layout /> : <Navigate to="/login" replace />}
            >
              <Route path="/" element={<Navigate to="/clusters" replace />} />
              <Route path="/clusters" element={<ClustersPage />} />
              <Route
                path="/users"
                element={
                  <RequireRole role="admin">
                    <UsersPage />
                  </RequireRole>
                }
              />
              <Route
                path="/secrets"
                element={
                  <RequireRole role="operator">
                    <SecretsPage />
                  </RequireRole>
                }
              />
              <Route
                path="/clusters/new"
                element={
                  <RequireRole role="admin">
                    <ClusterNewPage />
                  </RequireRole>
                }
              />
              <Route path="/clusters/:id" element={<ClusterDetailPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/account" element={<AccountPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </AuthContext.Provider>
  );
}
