import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Home from './pages/Home';
import WFA from './pages/WFA';
import Sensitivity from './pages/Sensitivity';
import MCS from './pages/MCS';
import PermTests from './pages/PermTests';
import Backtest from './pages/Backtest';

// Icon components for the navigation
const WFAIcon = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" />
        <path d="M7 16l4-8 4 5 5-9" />
    </svg>
);

const SensitivityIcon = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v6m0 6v10" />
        <path d="M21 12h-6m-6 0H1" />
        <path d="M18.364 5.636l-4.243 4.243m-4.242 4.242l-4.243 4.243" />
        <path d="M18.364 18.364l-4.243-4.243m-4.242-4.242L5.636 5.636" />
    </svg>
);

const MonteCarloIcon = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="5" height="5" rx="1" />
        <rect x="9" y="9" width="5" height="5" rx="1" />
        <rect x="17" y="17" width="5" height="5" rx="1" />
        <circle cx="4.5" cy="4.5" r="0.5" fill="currentColor" />
        <circle cx="11.5" cy="11.5" r="0.5" fill="currentColor" />
        <circle cx="19.5" cy="19.5" r="0.5" fill="currentColor" />
    </svg>
);

const PermutationIcon = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 3h5v5" />
        <path d="M8 3H3v5" />
        <path d="M21 3l-7 7" />
        <path d="M3 3l7 7" />
        <path d="M16 21h5v-5" />
        <path d="M8 21H3v-5" />
        <path d="M21 21l-7-7" />
        <path d="M3 21l7-7" />
    </svg>
);

const BacktestIcon = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
        <path d="M2 12h2" />
        <path d="M20 12h2" />
    </svg>
);

function NavLink({ to, icon: Icon, children }) {
    const location = useLocation();
    const isActive = location.pathname === '/' ? to === '/' : location.pathname.startsWith(to) && to !== '/';

    return (
        <Link
            to={to}
            className={`flex flex-col items-center justify-center gap-1 px-3 py-2 rounded-lg transition-all duration-200 min-w-[60px] group ${isActive
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                }`}
        >
            <Icon className={`w-5 h-5 transition-transform duration-200 ${isActive ? '' : 'group-hover:scale-105'}`} />
            <span className="text-[10px] font-medium tracking-wide uppercase">{children}</span>
        </Link>
    );
}

function Layout({ children }) {
    return (
        <div className="flex flex-col h-screen bg-background">
            {/* Top Header */}
            <header className="h-16 border-b bg-card flex items-center justify-center px-6 sticky top-0 z-10 shadow-sm">
                <Link to="/" className="flex flex-col items-center group cursor-pointer">
                    <h1 className="text-xl font-serif font-semibold text-foreground tracking-wide group-hover:text-primary transition-colors duration-300">
                        AlphaVerify
                    </h1>
                    <div className="h-0.5 w-12 bg-accent mt-1 rounded-full group-hover:w-16 transition-all duration-300"></div>
                </Link>
            </header>

            {/* Main Content */}
            <main className="flex-1 overflow-auto pb-20">
                {children}
            </main>

            {/* Bottom Navigation */}
            <nav className="fixed bottom-0 left-0 right-0 h-16 bg-card border-t shadow-lg">
                <div className="h-full max-w-lg mx-auto flex items-center justify-around px-2">
                    <NavLink to="/wfa" icon={WFAIcon}>WFA</NavLink>
                    <NavLink to="/sensitivity" icon={SensitivityIcon}>Sensitivity</NavLink>
                    <NavLink to="/mcs" icon={MonteCarloIcon}>Monte Carlo</NavLink>
                    <NavLink to="/permtests" icon={PermutationIcon}>Permutation</NavLink>
                    <NavLink to="/backtest" icon={BacktestIcon}>Backtest</NavLink>
                </div>
            </nav>
        </div>
    );
}

function App() {
    return (
        <Router>
            <Layout>
                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/wfa/*" element={<WFA />} />
                    <Route path="/sensitivity/*" element={<Sensitivity />} />
                    <Route path="/mcs/*" element={<MCS />} />
                    <Route path="/permtests/*" element={<PermTests />} />
                    <Route path="/backtest/*" element={<Backtest />} />
                </Routes>
            </Layout>
        </Router>
    );
}

export default App;
