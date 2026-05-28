import { useEffect, useState } from "react";
import api, { ROLE_LABELS } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Plus, UserPlus } from "lucide-react";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users");
      setUsers(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggleActive = async (u) => {
    await api.patch(`/users/${u.id}`, { is_active: !u.is_active });
    toast.success(u.is_active ? "User dinonaktifkan" : "User diaktifkan");
    load();
  };

  return (
    <div className="p-10" data-testid="admin-users-page">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Manajemen Pengguna</h1>
          <p className="text-sm text-zinc-500 mt-1">Tambah dan kelola akun internal sistem.</p>
        </div>
        <Button
          onClick={() => setOpen(true)}
          className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
          data-testid="add-user-button"
        >
          <UserPlus size={14} className="mr-1.5" /> Tambah Pengguna
        </Button>
      </header>

      <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 border-b border-zinc-200">
            <tr className="text-left">
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Nama</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Email</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Role</th>
              <th className="px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wide">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {loading ? (
              <tr><td colSpan={5} className="px-5 py-12 text-center text-zinc-500">Memuat...</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} data-testid={`user-row-${u.id}`}>
                  <td className="px-5 py-3 font-medium">{u.name}</td>
                  <td className="px-5 py-3 font-mono text-xs text-zinc-700">{u.email}</td>
                  <td className="px-5 py-3 text-zinc-700">{ROLE_LABELS[u.role] || u.role}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-sm border font-medium ${
                        u.is_active
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-zinc-100 text-zinc-500 border-zinc-200"
                      }`}
                    >
                      {u.is_active ? "Aktif" : "Nonaktif"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Button
                      onClick={() => toggleActive(u)}
                      size="sm"
                      variant="outline"
                      className="rounded-sm border-zinc-300 text-xs h-7"
                      data-testid={`toggle-user-${u.id}`}
                    >
                      {u.is_active ? "Nonaktifkan" : "Aktifkan"}
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {open && <AddUserDialog onClose={() => setOpen(false)} onCreated={load} />}
    </div>
  );
}

function AddUserDialog({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "hr_recruiter",
  });

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/users", form);
      toast.success("Pengguna ditambahkan");
      onClose();
      onCreated();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal menambah pengguna");
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white border border-zinc-200 rounded-sm w-full max-w-md p-6" data-testid="add-user-dialog">
        <h3 className="font-heading text-lg font-semibold tracking-tight mb-4">Tambah Pengguna</h3>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label className="text-xs uppercase">Nama</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="rounded-sm mt-1"
              data-testid="new-user-name"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">Email</Label>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
              className="rounded-sm mt-1 font-mono"
              data-testid="new-user-email"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">Kata Sandi</Label>
            <Input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={6}
              className="rounded-sm mt-1"
              data-testid="new-user-password"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">Role</Label>
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="w-full border border-zinc-300 rounded-sm text-sm h-10 px-3 mt-1"
              data-testid="new-user-role"
            >
              <option value="hr_recruiter">HR Recruiter</option>
              <option value="hiring_manager">Hiring Manager</option>
              <option value="admin_it">Admin IT</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} className="rounded-sm border-zinc-300">Batal</Button>
            <Button type="submit" className="rounded-sm bg-zinc-900 hover:bg-zinc-800" data-testid="submit-new-user">Simpan</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
