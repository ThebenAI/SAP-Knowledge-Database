import { ReactElement, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { getCurrentUser } from "./api/auth";
import { getStoredAuthToken, setStoredAuthToken } from "./api/client";
import { FolderImportPage } from "./pages/FolderImportPage";
import { KnowledgeItemDetailPage } from "./pages/KnowledgeItemDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { ReviewListPage } from "./pages/ReviewListPage";
import { UserManagementPage } from "./pages/UserManagementPage";
import type { User } from "./types/api";

type ProtectedRouteProps = {
  user: User | null;
  children: ReactElement;
};

function ProtectedRoute({ user, children }: ProtectedRouteProps) {
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

type AdminRouteProps = {
  user: User | null;
  children: ReactElement;
};

function AdminRoute({ user, children }: AdminRouteProps) {
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/import" replace />;
  return children;
}

export default function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      setIsCheckingAuth(false);
      return;
    }
    void getCurrentUser()
      .then((user) => setCurrentUser(user))
      .catch(() => {
        setStoredAuthToken(null);
        setCurrentUser(null);
      })
      .finally(() => setIsCheckingAuth(false));
  }, []);

  useEffect(() => {
    const onAuthRequired = () => {
      setStoredAuthToken(null);
      setCurrentUser(null);
    };
    window.addEventListener("auth:required", onAuthRequired);
    return () => window.removeEventListener("auth:required", onAuthRequired);
  }, []);

  const handleLoginSuccess = (token: string, user: User) => {
    setStoredAuthToken(token);
    setCurrentUser(user);
  };

  const handleLogout = () => {
    setStoredAuthToken(null);
    setCurrentUser(null);
  };

  if (isCheckingAuth) {
    return (
      <div className="app-shell">
        <div className="app-main">
          <p>Authentifizierung wird geprüft...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>SAP Knowledge Database</h1>
        {currentUser ? (
          <nav className="app-nav">
            <NavLink to="/import" className={({ isActive }) => (isActive ? "app-nav__link app-nav__link--active" : "app-nav__link")}>
              Import
            </NavLink>
            <NavLink to="/review" className={({ isActive }) => (isActive ? "app-nav__link app-nav__link--active" : "app-nav__link")}>
              Review
            </NavLink>
            {currentUser.role === "admin" && (
              <NavLink to="/admin/users" className={({ isActive }) => (isActive ? "app-nav__link app-nav__link--active" : "app-nav__link")}>
                Benutzer
              </NavLink>
            )}
            <span className="app-nav__user">{currentUser.username} ({currentUser.role})</span>
            <button type="button" className="button-secondary app-nav__logout" onClick={handleLogout}>
              Logout
            </button>
          </nav>
        ) : null}
      </header>
      <div className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to={currentUser ? "/import" : "/login"} replace />} />
          <Route path="/login" element={currentUser ? <Navigate to="/import" replace /> : <LoginPage onLoginSuccess={handleLoginSuccess} />} />
          <Route
            path="/import"
            element={
              <ProtectedRoute user={currentUser}>
                <FolderImportPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/review"
            element={
              <ProtectedRoute user={currentUser}>
                <ReviewListPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/knowledge-items/:itemId"
            element={
              <ProtectedRoute user={currentUser}>
                <KnowledgeItemDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <AdminRoute user={currentUser}>
                <UserManagementPage />
              </AdminRoute>
            }
          />
        </Routes>
      </div>
    </div>
  );
}
