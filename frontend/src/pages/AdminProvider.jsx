import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Check, Plus, Zap } from "lucide-react";

export default function AdminProvider() {
  const [providers, setProviders] = useState([]);
  const [testing, setTesting] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/config/ai-providers");
      setProviders(data);
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

  const handleTest = async (p) => {
    setTesting(true);
    try {
      const { data } = await api.post("/config/ai-providers/test", {
        provider_type: p.provider_type,
        base_url: p.base_url || "",
        api_key: p.api_key && !p.api_key.startsWith("***") ? p.api_key : "",
        llm_provider: p.llm_provider,
        model_name: p.model_name,
      });
      if (data.success) toast.success("Koneksi berhasil: " + data.response);
      else toast.error("Koneksi gagal: " + data.error);
    } finally {
      setTesting(false);
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
        <div className="space-y-3">
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
                  {!p.is_active && (
                    <Button
                      onClick={() => activate(p.id)}
                      size="sm"
                      className="rounded-sm bg-zinc-900 hover:bg-zinc-800"
                      data-testid={`activate-provider-${p.id}`}
                    >
                      <Check size={12} className="mr-1" /> Aktifkan
                    </Button>
                  )}
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

function AddProviderDialog({ onCreated }) {
  const [open, setOpen] = useState(false);
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
          <div className="flex justify-end gap-2 pt-2">
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
        </form>
      </div>
    </div>
  );
}
