import { NavLink, Route, Routes } from 'react-router-dom';
import { HeartHandshake } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AdminTokenButton } from '@/components/AdminTokenButton';
import { IntegrationStatusBar } from '@/components/IntegrationStatusBar';
import { ResidentsOverview } from '@/pages/ResidentsOverview';
import { ResidentDetail } from '@/pages/ResidentDetail';
import { TrustPage } from '@/pages/TrustPage';

function NavTab({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
          isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground',
        )
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                <HeartHandshake className="h-5 w-5" />
              </div>
              <div className="leading-tight">
                <div className="font-bold">Quietcare</div>
                <div className="text-xs text-muted-foreground">Caretaker</div>
              </div>
            </div>
            <nav className="flex items-center gap-1">
              <NavTab to="/">Residents</NavTab>
              <NavTab to="/trust">Trust</NavTab>
            </nav>
          </div>
          <AdminTokenButton />
        </div>
      </header>

      <main className="container py-8">
        <Routes>
          <Route path="/" element={<ResidentsOverview />} />
          <Route path="/elders/:id" element={<ResidentDetail />} />
          <Route path="/trust" element={<TrustPage />} />
        </Routes>
      </main>

      <footer className="border-t border-border">
        <div className="container flex flex-wrap items-center justify-between gap-3 py-4">
          <IntegrationStatusBar />
          <span className="text-xs text-muted-foreground">
            911 dispatch always requires explicit, audited confirmation.
          </span>
        </div>
      </footer>
    </div>
  );
}
