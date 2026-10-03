import type { ReactNode } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";

import type { Role } from "./api";
import { AuthProvider, useAuth } from "./auth";
import { Assign } from "./pages/Assign";
import { ClientRequests } from "./pages/ClientRequests";
import { Login } from "./pages/Login";
import { NewRequest } from "./pages/NewRequest";
import { OperatorRequests } from "./pages/OperatorRequests";
import { Button } from "./ui";

/**
 * Shows the page only to a signed-in user with one of the given roles.
 * Navigation only: the server enforces every rule regardless.
 */
function Gate({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

/** Top bar with navigation for the user's role and sign out. */
function Shell() {
  const { user, signOut } = useAuth();
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          Handoff
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Requests
          </NavLink>
          {user?.role === "client" && <NavLink to="/requests/new">New request</NavLink>}
        </nav>
        <span className="topbar__user">
          {user?.name} <span className="muted">· {user?.role}</span>
        </span>
        <Button variant="plain" onClick={signOut}>
          Sign out
        </Button>
      </header>
      <Outlet />
    </>
  );
}

function Home() {
  return useAuth().user?.role === "client" ? <ClientRequests /> : <OperatorRequests />;
}

/** Application routes. */
export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <Gate>
                <Shell />
              </Gate>
            }
          >
            <Route index element={<Home />} />
            <Route path="/requests/new" element={<Gate roles={["client"]}>{<NewRequest />}</Gate>} />
            <Route
              path="/requests/:requestId/assign"
              element={<Gate roles={["operator", "admin"]}>{<Assign />}</Gate>}
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
