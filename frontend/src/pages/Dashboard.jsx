import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { SCORE_BAND, BAND_COLORS } from "@/lib/api";
import { Briefcase, Users, Sparkles, TrendingUp } from "lucide-react";

function StatCard({ icon: Icon, label, value, testId }) {
  return (
    <div
      className="bg-white border border-zinc-200 p-5 rounded-sm"
      data-testid={testId}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-zinc-500 font-medium">
            {label}
          </div>
          <div className="font-heading text-3xl font-semibold mt-2 tracking-tight tabular-nums">
            {value}
          </div>
        </div>
        <div className="w-9 h-9 bg-zinc-100 flex items-center justify-center rounded-sm text-zinc-700">
          <Icon size={16} />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data));
  }, []);

  if (!stats) {
    return (
      <div className="p-10 text-zinc-500" data-testid="dashboard-loading">
        Memuat data...
      </div>
    );
  }

  const dist = stats.score_distribution || { low: 0, mid: 0, high: 0 };
  const totalDist = (dist.low || 0) + (dist.mid || 0) + (dist.high || 0);

  return (
    <div className="p-10" data-testid="dashboard-page">
      <header className="mb-10">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Beranda</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Ringkasan aktivitas rekrutmen hari ini.
        </p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        <StatCard
          icon={Briefcase}
          label="Lowongan Aktif"
          value={stats.active_jobs}
          testId="stat-active-jobs"
        />
        <StatCard
          icon={Users}
          label="Total Kandidat"
          value={stats.total_candidates}
          testId="stat-total-candidates"
        />
        <StatCard
          icon={Sparkles}
          label="Diproses Hari Ini"
          value={stats.processed_today}
          testId="stat-processed-today"
        />
        <StatCard
          icon={TrendingUp}
          label="Total Screening"
          value={stats.total_screenings}
          testId="stat-total-screenings"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Score Distribution */}
        <div className="lg:col-span-1 bg-white border border-zinc-200 p-6 rounded-sm" data-testid="score-distribution">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-heading text-base font-semibold tracking-tight">
              Distribusi Skor
            </h3>
            <span className="text-xs text-zinc-500 font-mono">{totalDist} hasil</span>
          </div>

          <div className="space-y-4">
            {[
              { key: "high", label: "Skor Tinggi (75-100)", count: dist.high, band: "high" },
              { key: "mid", label: "Skor Sedang (40-74)", count: dist.mid, band: "mid" },
              { key: "low", label: "Skor Rendah (0-39)", count: dist.low, band: "low" },
            ].map((row) => {
              const pct = totalDist > 0 ? Math.round((row.count / totalDist) * 100) : 0;
              const barColor = {
                high: "bg-emerald-600",
                mid: "bg-amber-500",
                low: "bg-rose-600",
              }[row.band];
              return (
                <div key={row.key} data-testid={`dist-${row.key}`}>
                  <div className="flex justify-between items-baseline mb-1.5">
                    <span className="text-xs text-zinc-700">{row.label}</span>
                    <span className="text-xs font-mono tabular-nums">
                      <span className="font-semibold">{row.count}</span>
                      <span className="text-zinc-400 ml-1">· {pct}%</span>
                    </span>
                  </div>
                  <div className="h-1.5 bg-zinc-100 rounded-sm overflow-hidden">
                    <div
                      className={`h-full ${barColor} transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Jobs */}
        <div className="lg:col-span-2 bg-white border border-zinc-200 p-6 rounded-sm" data-testid="recent-jobs">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-heading text-base font-semibold tracking-tight">
              Lowongan Terbaru
            </h3>
            <button
              onClick={() => navigate("/jobs")}
              className="text-xs text-zinc-700 hover:text-zinc-900 underline-offset-2 hover:underline"
              data-testid="view-all-jobs"
            >
              Lihat semua →
            </button>
          </div>

          {stats.recent_jobs.length === 0 ? (
            <div className="text-sm text-zinc-500 py-8 text-center">
              Belum ada lowongan. Buat lowongan pertama Anda dari halaman Lowongan.
            </div>
          ) : (
            <div className="divide-y divide-zinc-200 -mx-6">
              {stats.recent_jobs.map((j) => (
                <button
                  key={j.id}
                  onClick={() => navigate(`/jobs/${j.id}`)}
                  data-testid={`recent-job-${j.id}`}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-zinc-50 text-left transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">{j.title}</div>
                    <div className="text-xs text-zinc-500 mt-0.5 truncate">
                      {j.department || j.target_position || "—"} ·{" "}
                      {(j.criteria || []).length} kriteria
                    </div>
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-sm border font-medium ${
                      j.status === "active"
                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                        : j.status === "draft"
                        ? "bg-zinc-50 text-zinc-600 border-zinc-200"
                        : "bg-zinc-100 text-zinc-500 border-zinc-200"
                    }`}
                    data-testid={`job-status-${j.id}`}
                  >
                    {j.status}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
