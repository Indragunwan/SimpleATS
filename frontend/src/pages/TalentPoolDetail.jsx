import { useEffect, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import api, { API, BAND_COLORS, RECOMMENDATION_LABELS, SCORE_BAND } from "@/lib/api";
import { ArrowLeft, Mail, Phone, FileText } from "lucide-react";

export default function TalentPoolDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get(`/talent-pool/${id}`).then((r) => setData(r.data));
  }, [id]);

  if (!data) return <div className="p-10 text-zinc-500">Memuat...</div>;
  const c = data.candidate;
  const parsed = c.parsed || {};
  const screenings = data.screenings || [];

  function calculateAge(birthDateStr) {
    if (!birthDateStr) return null;
    const birthDate = new Date(birthDateStr);
    if (isNaN(birthDate.getTime())) return null;
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  }

  const softKeywords = [
    "hr", "recruitment", "human resources", "communication", "leadership", "budgeting", 
    "management", "teamwork", "negotiation", "problem solving", "time management", 
    "critical thinking", "adaptability", "conflict resolution", "interpersonal", 
    "public speaking", "asset", "administration", "pengelolaan", "komunikasi", "kepemimpinan",
    "public relation", "presentasi", "adaptif", "analitis", "kreatif", "negosiasi"
  ];
  
  let hardSkills = parsed.hard_skills || [];
  let softSkills = parsed.soft_skills || [];
  
  if (hardSkills.length === 0 && softSkills.length === 0 && parsed.skills) {
    hardSkills = [];
    softSkills = [];
    parsed.skills.forEach(skill => {
      const lower = skill.toLowerCase();
      if (softKeywords.some(kw => lower.includes(kw))) {
        softSkills.push(skill);
      } else {
        hardSkills.push(skill);
      }
    });
  }

  return (
    <div className="p-10" data-testid="pool-detail-page">
      <button
        onClick={() => navigate("/talent-pool", { state: location.state })}
        className="text-xs text-zinc-500 hover:text-zinc-900 inline-flex items-center gap-1 mb-4"
        data-testid="back-to-pool"
      >
        <ArrowLeft size={12} /> Kembali ke Talent Pool
      </button>

      <div className="bg-white border border-zinc-200 rounded-sm p-6 mb-4">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 bg-zinc-900 text-white flex items-center justify-center rounded-sm font-heading text-xl font-semibold">
            {(c.name || "?").split(" ").map((n) => n[0]).slice(0, 2).join("")}
          </div>
          <div>
            <h1 className="font-heading text-2xl font-semibold tracking-tight">{c.name}</h1>
            <div className="text-sm text-zinc-500 mt-1 flex items-center gap-4 flex-wrap">
              {c.email && <span className="inline-flex items-center gap-1"><Mail size={12} />{c.email}</span>}
              {c.phone && <span className="inline-flex items-center gap-1"><Phone size={12} />{c.phone}</span>}
              <span className="text-xs">· {parsed.years_of_experience || 0} thn pengalaman</span>
              {c.id && (
                <a
                  href={`${API}/candidates/${c.id}/cv`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1 rounded border border-indigo-200 transition-colors ml-2"
                >
                  <FileText size={12} /> Lihat CV Asli
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-zinc-200 rounded-sm p-6">
          <h3 className="font-heading text-base font-semibold tracking-tight mb-4">Profil Kandidat</h3>

          {/* Grid Informasi Kandidat Baru */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 bg-zinc-50 p-4 rounded border border-zinc-150 text-sm">
            <div>
              <span className="text-zinc-500 block text-xs uppercase tracking-wider font-medium">Total Pengalaman Kerja</span>
              <span className="font-semibold text-zinc-800">{parsed.years_of_experience || 0} tahun</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-xs uppercase tracking-wider font-medium">Gender</span>
              <span className="font-semibold text-zinc-800 capitalize">{parsed.gender || "Tidak diketahui"}</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-xs uppercase tracking-wider font-medium">Usia</span>
              <span className="font-semibold text-zinc-800">
                {parsed.birth_date ? `${calculateAge(parsed.birth_date)} tahun (${parsed.birth_date})` : "Tidak diketahui"}
              </span>
            </div>
            <div>
              <span className="text-zinc-500 block text-xs uppercase tracking-wider font-medium">Alamat</span>
              <span className="font-semibold text-zinc-800">{parsed.address || "Tidak diketahui"}</span>
            </div>
          </div>

          {parsed.summary && <p className="text-sm text-zinc-700 mb-6 leading-relaxed">{parsed.summary}</p>}

          {/* Keahlian (Hard Skill & Soft Skill) */}
          <Section title="Keahlian">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
              <div className="bg-zinc-50/50 p-3 rounded border border-zinc-100">
                <div className="text-xs font-semibold text-zinc-600 mb-2 border-b pb-1">⚡ Hard Skill</div>
                {hardSkills && hardSkills.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {hardSkills.map((sk, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 bg-white text-zinc-700 rounded border border-zinc-200">
                        {sk}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-zinc-400 font-normal italic">—</span>
                )}
              </div>
              <div className="bg-zinc-50/50 p-3 rounded border border-zinc-100">
                <div className="text-xs font-semibold text-zinc-600 mb-2 border-b pb-1">🤝 Soft Skill</div>
                {softSkills && softSkills.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {softSkills.map((sk, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 bg-white text-zinc-700 rounded border border-zinc-200">
                        {sk}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-zinc-400 font-normal italic">—</span>
                )}
              </div>
            </div>
          </Section>

          {parsed.work_history?.length > 0 && (
            <Section title="Riwayat Pekerjaan">
              <div className="space-y-3">
                {parsed.work_history.map((w, i) => (
                  <div key={i} className="border-l-2 border-zinc-200 pl-3">
                    <div className="font-medium text-sm">{w.position}</div>
                    <div className="text-xs text-zinc-500">
                      {w.company} · {w.duration}
                    </div>
                    {w.achievements?.length > 0 && (
                      <ul className="mt-1 text-xs text-zinc-600 list-disc pl-4 space-y-0.5">
                        {w.achievements.slice(0, 3).map((a, j) => (
                          <li key={j}>{a}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {parsed.education?.length > 0 && (
            <Section title="Pendidikan">
              <div className="space-y-2">
                {parsed.education.map((e, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium">{e.degree}</div>
                    <div className="text-xs text-zinc-500">
                      {e.institution} · {e.year}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {parsed.certifications?.length > 0 && (
            <Section title="Training atau Sertifikasi">
              <ul className="text-sm text-zinc-700 list-disc pl-4 space-y-1">
                {parsed.certifications.map((cert, i) => (
                  <li key={i}>{cert}</li>
                ))}
              </ul>
            </Section>
          )}

          {parsed.achievements?.length > 0 && (
            <Section title="Achievement">
              <ul className="text-sm text-zinc-700 list-disc pl-4 space-y-1">
                {parsed.achievements.map((ach, i) => (
                  <li key={i} className="text-zinc-800 font-medium">{ach}</li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        <div className="lg:col-span-1 bg-white border border-zinc-200 rounded-sm p-6" data-testid="screening-history">
          <h3 className="font-heading text-base font-semibold tracking-tight mb-4">Riwayat Screening</h3>
          {screenings.length === 0 ? (
            <div className="text-sm text-zinc-400">Belum pernah di-screening</div>
          ) : (
            <div className="space-y-2">
              {screenings.map((s) => {
                const band = SCORE_BAND(s.total_score);
                return (
                  <button
                    key={s.id}
                    onClick={() => navigate(`/screenings/${s.id}`)}
                    data-testid={`history-screening-${s.id}`}
                    className="w-full text-left p-3 border border-zinc-200 hover:border-zinc-900 rounded-sm transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{s.job_title}</div>
                        <div className="text-xs text-zinc-500 mt-0.5">{s.job_department || "—"}</div>
                        <div className="text-xs text-zinc-500 mt-1">
                          {RECOMMENDATION_LABELS[s.recommendation]}
                          {s.decision !== "pending" && (
                            <span className="ml-2 text-zinc-900 font-medium">· {s.decision}</span>
                          )}
                        </div>
                      </div>
                      <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded-sm border ${BAND_COLORS[band]}`}>
                        {s.total_score}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mb-5">
      <div className="text-xs uppercase tracking-wider text-zinc-500 mb-2 font-medium">{title}</div>
      {children}
    </div>
  );
}
