import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/api";
import {
  LayoutDashboard,
  Briefcase,
  Settings,
  Users,
  LogOut,
  Heart,
  UsersRound,
} from "lucide-react";

const NAV = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Beranda", roles: ["hr_recruiter", "hiring_manager", "admin_it"] },
  { to: "/jobs", icon: Briefcase, label: "Lowongan", roles: ["hr_recruiter", "hiring_manager", "admin_it"] },
  { to: "/talent-pool", icon: UsersRound, label: "Talent Pool", roles: ["hr_recruiter", "hiring_manager", "admin_it"] },
  { to: "/admin/provider", icon: Settings, label: "Konfigurasi AI", roles: ["admin_it"] },
  { to: "/admin/users", icon: Users, label: "Pengguna", roles: ["admin_it"] },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (!user) return null;

  const initials = user.name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 flex print:block print:bg-white" data-testid="app-shell">
      {/* Sidebar */}
      <aside className="w-60 border-r border-zinc-200 bg-white flex flex-col print:hidden" data-testid="sidebar">
        <div className="px-5 py-5 border-b border-zinc-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-rose-600 text-white flex items-center justify-center rounded-sm">
              <Heart size={16} fill="currentColor" />
            </div>
            <div>
              <div className="font-heading text-sm font-semibold tracking-tight leading-none">HEARTH</div>
              <div className="text-xs text-zinc-500 mt-1">HR Applicant Tracking</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.filter((n) => n.roles.includes(user.role)).map((item) => {
            const Icon = item.icon;
            const active = location.pathname === item.to || (item.to !== "/dashboard" && location.pathname.startsWith(item.to));
            return (
              <Link
                key={item.to}
                to={item.to}
                data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                className={`flex items-center gap-3 px-3 py-2 text-sm rounded-sm transition-colors ${
                  active
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-zinc-200 p-3">
          <button
            onClick={() => navigate(`/profile`)}
            className="w-full flex items-center gap-3 px-2 py-2 rounded-sm hover:bg-zinc-100 transition-colors text-left"
            data-testid="profile-button"
          >
            <div className="w-9 h-9 bg-zinc-900 text-white text-xs font-medium flex items-center justify-center rounded-sm font-heading">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user.name}</div>
              <div className="text-xs text-zinc-500 truncate">{ROLE_LABELS[user.role]}</div>
            </div>
          </button>
          <button
            onClick={logout}
            data-testid="logout-button"
            className="mt-2 w-full flex items-center justify-center gap-2 px-2 py-2 text-xs text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100 rounded-sm"
          >
            <LogOut size={14} />
            Keluar
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-x-hidden" data-testid="main-content">
        {children}
      </main>
    </div>
  );
}
