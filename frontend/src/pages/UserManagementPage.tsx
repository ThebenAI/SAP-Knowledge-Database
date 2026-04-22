import { FormEvent, useEffect, useState } from "react";
import { createUser, listUsers, resetUserPassword, updateUser } from "../api/auth";
import type { User, UserRole } from "../types/api";

export function UserManagementPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<UserRole>("reviewer");
  const [newActive, setNewActive] = useState(true);

  const fetchUsers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benutzer konnten nicht geladen werden.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchUsers();
  }, []);

  const onCreateUser = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await createUser({
        username: newUsername.trim(),
        password: newPassword,
        role: newRole,
        is_active: newActive,
      });
      setNewUsername("");
      setNewPassword("");
      setNewRole("reviewer");
      setNewActive(true);
      setMessage("Benutzer wurde angelegt.");
      await fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benutzer konnte nicht angelegt werden.");
    } finally {
      setIsSaving(false);
    }
  };

  const onToggleActive = async (user: User) => {
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await updateUser(user.id, { is_active: !user.is_active });
      setMessage("Status aktualisiert.");
      await fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status konnte nicht aktualisiert werden.");
    } finally {
      setIsSaving(false);
    }
  };

  const onChangeRole = async (user: User, role: UserRole) => {
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await updateUser(user.id, { role });
      setMessage("Rolle aktualisiert.");
      await fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rolle konnte nicht aktualisiert werden.");
    } finally {
      setIsSaving(false);
    }
  };

  const onResetPassword = async (user: User) => {
    const nextPassword = window.prompt(`Neues Passwort für ${user.username}:`);
    if (nextPassword === null) return;
    if (!nextPassword.trim()) return;
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await resetUserPassword(user.id, nextPassword);
      setMessage("Passwort wurde zurückgesetzt.");
      window.alert("Passwort wurde erfolgreich zurückgesetzt.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Passwort konnte nicht zurückgesetzt werden.";
      setError(msg);
      window.alert(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="page">
      <section className="page-header card">
        <h2>Benutzerverwaltung</h2>
        <p>Admins können Benutzer erstellen, aktivieren/deaktivieren, Rollen ändern und Passwörter zurücksetzen.</p>
      </section>

      <section className="card">
        <h3>Neuen Benutzer anlegen</h3>
        <form className="filters filters--compact" onSubmit={onCreateUser}>
          <label>
            Benutzername
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} required />
          </label>
          <label>
            Passwort
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label>
            Rolle
            <select value={newRole} onChange={(e) => setNewRole(e.target.value as UserRole)}>
              <option value="reviewer">reviewer</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <label className="inline-check">
            <input type="checkbox" checked={newActive} onChange={(e) => setNewActive(e.target.checked)} />
            Aktiv
          </label>
          <button type="submit" disabled={isSaving}>
            {isSaving ? "Speichern..." : "Benutzer erstellen"}
          </button>
        </form>
      </section>

      <section className="card">
        <h3>Benutzer</h3>
        {isLoading && <p>Lade Benutzer...</p>}
        {!isLoading && users.length === 0 && <p>Keine Benutzer vorhanden.</p>}
        {!isLoading && users.length > 0 && (
          <div className="review-table-wrap">
            <table className="review-table">
              <thead>
                <tr>
                  <th>Benutzername</th>
                  <th>Rolle</th>
                  <th>Status</th>
                  <th>Erstellt</th>
                  <th>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>
                      <select value={user.role} onChange={(e) => void onChangeRole(user, e.target.value as UserRole)} disabled={isSaving}>
                        <option value="reviewer">reviewer</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>{user.is_active ? "Aktiv" : "Inaktiv"}</td>
                    <td>{new Date(user.created_at).toLocaleString()}</td>
                    <td className="actions">
                      <button type="button" className="button-secondary" onClick={() => void onToggleActive(user)} disabled={isSaving}>
                        {user.is_active ? "Deaktivieren" : "Aktivieren"}
                      </button>
                      <button type="button" onClick={() => void onResetPassword(user)} disabled={isSaving}>
                        Passwort zurücksetzen
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {error && <p className="error">{error}</p>}
        {message && <p className="review-save-success">{message}</p>}
      </section>
    </main>
  );
}
