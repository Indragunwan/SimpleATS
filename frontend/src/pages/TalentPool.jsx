import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { BAND_COLORS, SCORE_BAND } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Search, Users } from "lucide-react";

export default function TalentPool() {
  const [pool, setPool] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get("/talent-pool")
      .then((r) => setPool(r.data))
      .finally(() => setLoading(false));
  }, []);

  const filtered = pool.filter(
    (c) =>
      search === "" ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase()) ||
      c.top_skills.some((s) => s.toLowerCase().includes(search.toLowerCase()))
  );

  const stats = {
    total: pool.length,
    high: pool.filter((c) => c.best_score >= 75).length,
    screened: pool.filter((c) => c.screenings_count > 0).length,
    shortlisted: pool.filter((c) => c.shortlisted_count > 0).length,
  };

  return (
    <div className="p-10" data-testid="talent-pool-page">
      <header className="mb-8">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Talent Pool</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Semua kandidat ter-parsing lintas lowongan. Gunakan untuk re-screening cepat ke JD baru.
        </p>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <PoolStat label="Total Kandidat" value={stats.total} testId="pool-total" />
        <PoolStat label="Skor Tinggi (≥75)" value={stats.high} accent="emerald" testId="pool-high" />
        <PoolStat label="Pernah Di-screening" value={stats.screened} testId="pool-screened" />
        <PoolStat label="Pernah Shortlist" value={stats.shortlisted} accent="emerald" testId="pool-shortlisted" />
      </div>

      <div className="bg-white border border-zinc-200 rounded-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-zinc-200 flex items-center justify-between gap-3">
          <div className="text-xs text-zinc-500">{filtered.length} ditampilkan</div>
          <div className="relative w-72">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
            <Input
              placeholder="Cari nama, email, atau skill..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-sm h-8 text-xs pl-7"
              data-testid="pool-search"
            />
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-zinc-50/60 border-b border-zinc-200">
            <tr className="text-left">
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Kandidat</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Posisi Terakhir</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide">Keahlian</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Exp</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Skor Terbaik</th>
              <th className="px-5 py-2.5 text-xs font-medium text-zinc-500 uppercase tracking-wide text-center">Screenings</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {loading ? (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-zinc-500">Memuat...</td></tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-16 text-center">
                  <Users className="mx-auto text-zinc-300 mb-3" size={32} />
                  <div className="text-zinc-700 font-medium mb-1">Pool masih kosong</div>
                  <div className="text-sm text-zinc-500">
                    Unggah CV dari halaman Lowongan untuk mengisi Talent Pool.
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((c) => (
                <tr
                  key={c.id}
                  className="hover:bg-zinc-50/80 cursor-pointer"
                  onClick={() => navigate(`/talent-pool/${c.id}`)}
                  data-testid={`pool-row-${c.id}`}
                >
                  <td className="px-5 py-3">
                    <div className="font-medium text-zinc-900">{c.name}</div>
                    <div className="text-xs text-zinc-500 font-mono mt-0.5">{c.email || "—"}</div>
                  </td>
                  <td className="px-5 py-3 text-zinc-700">{c.current_position || "—"}</td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.top_skills.slice(0, 4).map((s, i) => (
                        <span key={i} className="text-xs px-1.5 py-0.5 bg-zinc-100 text-zinc-700 rounded-sm">
                          {s}
                        </span>
                      ))}
                      {c.top_skills.length > 4 && (
                        <span className="text-xs text-zinc-400">+{c.top_skills.length - 4}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-center text-zinc-700 tabular-nums text-xs">
                    {c.years_of_experience} thn
                  </td>
                  <td className="px-5 py-3 text-center">
                    {c.screenings_count > 0 ? (
                      <span
                        className={`inline-block min-w-[42px] text-center font-mono tabular-nums font-semibold text-xs px-2 py-0.5 rounded-sm border ${BAND_COLORS[SCORE_BAND(c.best_score)]}`}
                      >
                        {c.best_score}
                      </span>
                    ) : (
                      <span className="text-xs text-zinc-400">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-center">
                    <span className="text-xs text-zinc-700 tabular-nums">{c.screenings_count}</span>
                    {c.shortlisted_count > 0 && (
                      <span className="ml-1 text-xs text-emerald-700">
                        ({c.shortlisted_count}✓)
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PoolStat({ label, value, accent, testId }) {
  return (
    <div className="bg-white border border-zinc-200 p-4 rounded-sm" data-testid={testId}>
      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
      <div
        className={`font-heading text-3xl font-semibold tabular-nums mt-1.5 tracking-tight ${
          accent === "emerald" ? "text-emerald-700" : "text-zinc-900"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
