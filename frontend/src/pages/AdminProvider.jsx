import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Check, Plus, Zap, Cpu, Brain, Save, Trash2, Edit, X } from "lucide-react";

export default function AdminProvider() {
  const [providers, setProviders] = useState([]);
  const [assignments, setAssignments] = useState({
    parsing_provider_id: "",
    scoring_provider_id: "",
  });
  const [testing, setTesting] = useState(false);
  const [savingAssign, setSavingAssign] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editingProvider, setEditingProvider] = useState(null);
  const [editOpen, setEditOpen] = useState(false);

  const triggerEdit = (p) => {
    setEditingProvider(p);
    setEditOpen(true);
  };

  const load = async () => {
    setLoading(true);
    try {
      const [p, a] = await Promise.all([
        api.get("/config/ai-providers"),
        api.get("/config/task-assignments"),
      ]);
      setProviders(p.data);
      setAssignments({
        parsing_provider_id: a.data.parsing_provider_id || "",
        scoring_provider_id: a.data.scoring_provider_id || "",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const activate = async (id) => {
    await api.patch(`/config/ai-providers/${id}`, { is_active: true });
    toast.success("Provider diaktifkan");
    load();
  };

  const deactivate = async (id) => {
    await api.patch(`/config/ai-providers/${id}`, { is_active: false });
    toast.success("Provider dinonaktifkan");
    load();
  };

  const saveAssignments = async () => {
    setSavingAssign(true);
    try {
      await api.put("/config/task-assignments", {
        parsing_provider_id: assignments.parsing_provider_id || null,
        scoring_provider_id: assignments.scoring_provider_id || null,
      });
      toast.success("Penugasan model disimpan");
    } catch (err) {
      toast.error("Gagal menyimpan penugasan");
    } finally {
      setSavingAssign(false);
    }
  };

  const handleTest = async (p) => {
    setTesting(true);
    try {
      const { data } = await api.post(`/config/ai-providers/${p.id}/test`);
      if (data.success) toast.success("Koneksi berhasil: " + data.response);
      else toast.error("Koneksi gagal: " + data.error);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Gagal mengetes koneksi");
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Apakah Anda yakin ingin menghapus provider ini?")) return;
    try {
      await api.delete(`/config/ai-providers/${id}`);
      toast.success("Provider berhasil dihapus");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Gagal menghapus provider");
    }
  };

  return (
    <div className="p-10" data-testid="admin-provider-page">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Konfigurasi AI Provider</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Kelola provider LLM yang digunakan untuk ekstraksi JD, parsing CV, dan scoring.
          </p>
        </div>
        <AddProviderDialog onCreated={load} />
      </header>

      {loading ? (
        <div className="text-zinc-500 text-sm">Memuat...</div>
      ) : (
        <div className="space-y-6">
          {/* Task model assignment panel */}
          <div className="bg-white border border-zinc-200 rounded-sm p-5" data-testid="task-assignment-panel">
            <div className="flex items-start justify-between mb-1">
              <div>
                <h3 className="font-heading text-base font-semibold tracking-tight">
                  Penugasan Model per Tugas
                </h3>
                <p className="text-xs text-zinc-500 mt-1 max-w-2xl">
                  Optimasi biaya: gunakan model cepat & murah (Gemini Flash) untuk parsing struktural,
                  dan model premium (Claude/GPT) hanya untuk scoring yang butuh judgment. Jika dikosongkan,
                  akan memakai provider yang ditandai <span className="font-semibold">AKTIF</span> sebagai fallback.
                </p>
              </div>
              <Button
                onClick={saveAssignments}
                disabled={savingAssign}
                size="sm"
                className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
                data-testid="save-task-assignments"
              >
                <Save size={12} className="mr-1.5" />
                {savingAssign ? "Menyimpan..." : "Simpan"}
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
              <TaskAssignField
                icon={Cpu}
                title="Parsing"
                subtitle="Ekstraksi kriteria JD + parsing CV (struktural)"
                hint="Rekomendasi: Gemini 3 Flash / 2.5 Flash · ~Rp 5-20/CV"
                value={assignments.parsing_provider_id}
                onChange={(v) => setAssignments({ ...assignments, parsing_provider_id: v })}
                providers={providers}
                testId="assign-parsing"
              />
              <TaskAssignField
                icon={Brain}
                title="Scoring & Rationale"
                subtitle="Semantic matching 5 dimensi + narasi rationale (judgment)"
                hint="Rekomendasi: Claude Sonnet 4.6 atau GPT-5.4 untuk kualitas · atau Flash untuk hemat"
                value={assignments.scoring_provider_id}
                onChange={(v) => setAssignments({ ...assignments, scoring_provider_id: v })}
                providers={providers}
                testId="assign-scoring"
              />
            </div>
          </div>

          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium pt-2">
            Daftar Provider
          </div>
          {providers.map((p) => (
            <div
              key={p.id}
              className={`bg-white border rounded-sm p-5 ${
                p.is_active ? "border-zinc-900" : "border-zinc-200"
              }`}
              data-testid={`provider-card-${p.id}`}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-heading font-semibold tracking-tight">{p.name}</span>
                    {p.is_active && (
                      <span className="text-xs px-2 py-0.5 rounded-sm bg-zinc-900 text-white font-medium">
                        AKTIF
                      </span>
                    )}
                    {assignments.parsing_provider_id === p.id && (
                      <span className="text-xs px-2 py-0.5 rounded-sm bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                        PARSING
                      </span>
                    )}
                    {assignments.scoring_provider_id === p.id && (
                      <span className="text-xs px-2 py-0.5 rounded-sm bg-violet-50 text-violet-700 border border-violet-200 font-medium">
                        SCORING
                      </span>
                    )}
                    <span className="text-xs px-2 py-0.5 rounded-sm border border-zinc-200 bg-zinc-50 text-zinc-700">
                      {p.provider_type === "emergent" ? "Emergent Universal" : "Custom Provider"}
                    </span>
                  </div>
                  <div className="text-xs text-zinc-500 font-mono">
                    {p.llm_provider} · {p.model_name}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => handleTest(p)}
                    disabled={testing}
                    variant="outline"
                    size="sm"
                    className="rounded-sm border-zinc-300"
                    data-testid={`test-provider-${p.id}`}
                  >
                    <Zap size={12} className="mr-1" /> Test Koneksi
                  </Button>
                  <Button
                    onClick={() => triggerEdit(p)}
                    variant="outline"
                    size="sm"
                    className="rounded-sm border-zinc-300"
                    data-testid={`edit-provider-${p.id}`}
                  >
                    <Edit size={12} className="mr-1" /> Edit
                  </Button>
                  {p.is_active ? (
                    <Button
                      onClick={() => deactivate(p.id)}
                      size="sm"
                      variant="outline"
                      className="rounded-sm border-zinc-300 text-zinc-700 hover:bg-zinc-50"
                      data-testid={`deactivate-provider-${p.id}`}
                    >
                      <X size={12} className="mr-1" /> Nonaktifkan
                    </Button>
                  ) : (
                    <Button
                      onClick={() => activate(p.id)}
                      size="sm"
                      className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
                      data-testid={`activate-provider-${p.id}`}
                    >
                      <Check size={12} className="mr-1" /> Aktifkan
                    </Button>
                  )}
                  <Button
                    onClick={() => handleDelete(p.id)}
                    variant="destructive"
                    size="sm"
                    disabled={p.is_active}
                    title={p.is_active ? "Tidak bisa menghapus provider yang sedang aktif" : "Hapus provider"}
                    className="rounded-sm bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid={`delete-provider-${p.id}`}
                  >
                    <Trash2 size={12} className="mr-1" /> Hapus
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                <Field label="Base URL" value={p.base_url || "(default)"} />
                <Field label="API Key" value={p.api_key || "(Emergent Key)"} mono />
                <Field label="Temperature" value={p.temperature} />
                <Field label="Max Tokens" value={p.max_tokens} />
              </div>
            </div>
          ))}
        </div>
      )}
      {editingProvider && (
        <EditProviderDialog
          provider={editingProvider}
          onUpdated={load}
          open={editOpen}
          setOpen={setEditOpen}
        />
      )}
    </div>
  );
}

function Field({ label, value, mono }) {
  return (
    <div>
      <div className="text-zinc-500 uppercase tracking-wider text-[10px] mb-1">{label}</div>
      <div className={`text-zinc-900 ${mono ? "font-mono" : ""} truncate`}>{value || "—"}</div>
    </div>
  );
}

function TaskAssignField({ icon: Icon, title, subtitle, hint, value, onChange, providers, testId }) {
  return (
    <div className="border border-zinc-200 rounded-sm p-4">
      <div className="flex items-start gap-2 mb-3">
        <div className="w-7 h-7 bg-zinc-100 flex items-center justify-center rounded-sm text-zinc-700 mt-0.5">
          <Icon size={14} />
        </div>
        <div>
          <div className="text-sm font-medium">{title}</div>
          <div className="text-xs text-zinc-500 mt-0.5">{subtitle}</div>
        </div>
      </div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-zinc-300 rounded-sm text-sm h-10 px-3"
        data-testid={testId}
      >
        <option value="">— Pakai provider AKTIF (fallback) —</option>
        {providers.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} · {p.llm_provider}/{p.model_name}
          </option>
        ))}
      </select>
      <div className="text-xs text-zinc-400 mt-2 italic">{hint}</div>
    </div>
  );
}

function AddProviderDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [testingConn, setTestingConn] = useState(false);
  const [form, setForm] = useState({
    name: "",
    provider_type: "custom",
    base_url: "",
    api_key: "",
    llm_provider: "openai",
    model_name: "gpt-4o-mini",
    temperature: 0.2,
    max_tokens: 4000,
  });

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/config/ai-providers", form);
      toast.success("Provider ditambahkan");
      setOpen(false);
      onCreated();
    } catch (err) {
      toast.error("Gagal menambahkan provider");
    }
  };

  const testConnection = async () => {
    setTestingConn(true);
    try {
      const { data } = await api.post("/config/ai-providers/test", {
        provider_type: form.provider_type,
        base_url: form.base_url || "",
        api_key: form.api_key || "",
        llm_provider: form.llm_provider,
        model_name: form.model_name,
      });
      if (data.success) {
        toast.success("Koneksi berhasil: " + data.response);
      } else {
        toast.error("Koneksi gagal: " + data.error);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Terjadi kesalahan saat mengetes koneksi");
    } finally {
      setTestingConn(false);
    }
  };

  if (!open) {
    return (
      <Button
        onClick={() => setOpen(true)}
        className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
        data-testid="add-provider-button"
      >
        <Plus size={14} className="mr-1" /> Tambah Provider
      </Button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" data-testid="add-provider-dialog">
      <div className="bg-white rounded-sm border border-zinc-200 w-full max-w-md p-6">
        <h3 className="font-heading text-lg font-semibold tracking-tight mb-4">Tambah Provider Custom</h3>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label className="text-xs uppercase">Nama</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Contoh: OpenAI Production"
              className="rounded-sm mt-1"
              required
              data-testid="provider-name-input"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">Base URL</Label>
            <Input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              className="rounded-sm mt-1 font-mono"
              data-testid="provider-baseurl-input"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">API Key</Label>
            <Input
              type="password"
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder="sk-..."
              className="rounded-sm mt-1 font-mono"
              data-testid="provider-apikey-input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase">Provider</Label>
              <select
                value={form.llm_provider}
                onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}
                className="w-full border border-zinc-300 rounded-sm text-sm h-10 px-3 mt-1"
                data-testid="provider-llm-select"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>
            <div>
              <Label className="text-xs uppercase">Model</Label>
              <Input
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                className="rounded-sm mt-1 font-mono text-xs"
                data-testid="provider-model-input"
              />
            </div>
          </div>
          <div className="flex justify-between items-center pt-2">
            <Button
              type="button"
              onClick={testConnection}
              disabled={testingConn}
              variant="outline"
              size="sm"
              className="rounded-sm border-zinc-300"
              data-testid="dialog-test-connection"
            >
              <Zap size={12} className="mr-1" />
              {testingConn ? "Mengetes..." : "Test Koneksi"}
            </Button>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                className="rounded-sm border-zinc-300"
              >
                Batal
              </Button>
              <Button type="submit" className="rounded-sm bg-zinc-900 hover:bg-zinc-800" data-testid="submit-provider">
                Simpan
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditProviderDialog({ provider, onUpdated, open, setOpen }) {
  const [testingConn, setTestingConn] = useState(false);
  const [form, setForm] = useState({
    name: provider.name || "",
    provider_type: provider.provider_type || "custom",
    base_url: provider.base_url || "",
    api_key: provider.api_key || "",
    llm_provider: provider.llm_provider || "openai",
    model_name: provider.model_name || "gpt-4o-mini",
    temperature: provider.temperature ?? 0.2,
    max_tokens: provider.max_tokens ?? 4000,
  });

  useEffect(() => {
    if (provider) {
      setForm({
        name: provider.name || "",
        provider_type: provider.provider_type || "custom",
        base_url: provider.base_url || "",
        api_key: provider.api_key || "",
        llm_provider: provider.llm_provider || "openai",
        model_name: provider.model_name || "gpt-4o-mini",
        temperature: provider.temperature ?? 0.2,
        max_tokens: provider.max_tokens ?? 4000,
      });
    }
  }, [provider]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (payload.api_key && payload.api_key.startsWith("***")) {
        delete payload.api_key;
      }
      await api.patch(`/config/ai-providers/${provider.id}`, payload);
      toast.success("Provider berhasil diperbarui");
      setOpen(false);
      onUpdated();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Gagal memperbarui provider");
    }
  };

  const testConnection = async () => {
    setTestingConn(true);
    try {
      let res;
      if (form.api_key && form.api_key.startsWith("***")) {
        res = await api.post(`/config/ai-providers/${provider.id}/test`);
      } else {
        res = await api.post("/config/ai-providers/test", {
          provider_type: form.provider_type,
          base_url: form.base_url || "",
          api_key: form.api_key || "",
          llm_provider: form.llm_provider,
          model_name: form.model_name,
        });
      }
      const data = res.data;
      if (data.success) {
        toast.success("Koneksi berhasil: " + data.response);
      } else {
        toast.error("Koneksi gagal: " + data.error);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Terjadi kesalahan saat mengetes koneksi");
    } finally {
      setTestingConn(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" data-testid="edit-provider-dialog">
      <div className="bg-white rounded-sm border border-zinc-200 w-full max-w-md p-6">
        <h3 className="font-heading text-lg font-semibold tracking-tight mb-4">Edit Provider</h3>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label className="text-xs uppercase">Nama</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Contoh: OpenAI Production"
              className="rounded-sm mt-1"
              required
              data-testid="edit-provider-name-input"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">Base URL</Label>
            <Input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              className="rounded-sm mt-1 font-mono"
              data-testid="edit-provider-baseurl-input"
            />
          </div>
          <div>
            <Label className="text-xs uppercase">API Key</Label>
            <Input
              type="password"
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder="Biarkan apa adanya jika tidak ingin diubah"
              className="rounded-sm mt-1 font-mono"
              data-testid="edit-provider-apikey-input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase">Provider</Label>
              <select
                value={form.llm_provider}
                onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}
                className="w-full border border-zinc-300 rounded-sm text-sm h-10 px-3 mt-1"
                data-testid="edit-provider-llm-select"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>
            <div>
              <Label className="text-xs uppercase">Model</Label>
              <Input
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                className="rounded-sm mt-1 font-mono text-xs"
                data-testid="edit-provider-model-input"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs uppercase">Temperature</Label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={form.temperature}
                onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) || 0 })}
                className="rounded-sm mt-1"
                data-testid="edit-provider-temp-input"
              />
            </div>
            <div>
              <Label className="text-xs uppercase">Max Tokens</Label>
              <Input
                type="number"
                value={form.max_tokens}
                onChange={(e) => setForm({ ...form, max_tokens: parseInt(e.target.value) || 0 })}
                className="rounded-sm mt-1"
                data-testid="edit-provider-tokens-input"
              />
            </div>
          </div>
          <div className="flex justify-between items-center pt-2">
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={testConnection}
                disabled={testingConn}
                variant="outline"
                size="sm"
                className="rounded-sm border-zinc-300"
                data-testid="edit-dialog-test-connection"
              >
                <Zap size={12} className="mr-1" />
                {testingConn ? "Mengetes..." : "Test Koneksi"}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={provider.is_active}
                title={provider.is_active ? "Tidak bisa menghapus provider yang sedang aktif" : "Hapus provider"}
                onClick={async () => {
                  if (window.confirm("Apakah Anda yakin ingin menghapus provider ini?")) {
                    try {
                      await api.delete(`/config/ai-providers/${provider.id}`);
                      toast.success("Provider berhasil dihapus");
                      setOpen(false);
                      onUpdated();
                    } catch (err) {
                      toast.error(err.response?.data?.detail || "Gagal menghapus provider");
                    }
                  }
                }}
                className="rounded-sm bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="edit-dialog-delete-provider"
              >
                <Trash2 size={12} className="mr-1" /> Hapus
              </Button>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                className="rounded-sm border-zinc-300"
              >
                Batal
              </Button>
              <Button type="submit" className="rounded-sm bg-zinc-900 hover:bg-zinc-800" data-testid="edit-submit-provider">
                Simpan
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
