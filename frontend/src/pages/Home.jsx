import React from 'react';
import { TrendingUp, Activity, Shuffle, Settings, BarChart3 } from 'lucide-react';
import ToolCard from '../components/ui/ToolCard';

const Home = () => {
    return (
        <div className="max-w-6xl mx-auto p-8">
            <div className="text-center mb-12 py-10">
                <h1 className="text-4xl md:text-5xl font-serif font-semibold mb-4 text-foreground tracking-tight">
                    AlphaVerify SuperApp
                </h1>
                <div className="h-1 w-24 bg-accent mx-auto mb-6 rounded-full"></div>
                <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
                    Professional-grade strategy validation suite. Select a tool below to begin your analysis.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <ToolCard
                    to="/wfa"
                    icon={Settings}
                    title="Walk Forward Analysis"
                    description="Optimize strategy parameters over rolling time windows to verify robustness and adaptability."
                />

                <ToolCard
                    to="/backtest"
                    icon={TrendingUp}
                    title="Strategy Backtest"
                    description="Run historical simulations with precision execution modeling to evaluate past performance."
                />

                <ToolCard
                    to="/mcs"
                    icon={BarChart3}
                    title="Monte Carlo Simulation"
                    description="Assess risk by simulating thousands of possible future market conditions and equity paths."
                />

                <ToolCard
                    to="/permtests"
                    icon={Shuffle}
                    title="Permutation Tests"
                    description="Validate statistical significance by comparing your strategy against randomized market data."
                />

                <ToolCard
                    to="/sensitivity"
                    icon={Activity}
                    title="Sensitivity Analysis"
                    description="Stress-test parameter stability to identify optimal operating ranges and cliff edges."
                />

                {/* Placeholder for future tools to maintain grid balance if needed, or leave empty */}
            </div>
        </div>
    );
};

export default Home;
