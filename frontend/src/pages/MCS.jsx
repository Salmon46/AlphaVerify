import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Label } from '../components/ui/Label';
import { Upload, Play, CheckCircle, TrendingUp, BarChart2 } from 'lucide-react';
import FormSection from '../components/ui/FormSection';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const MCS = () => {
    const [file, setFile] = useState(null);
    const [config, setConfig] = useState({
        email: '',
        initial_capital: 10000,
        n_simulations: 4500
    });
    const [running, setRunning] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleRunSimulation = async () => {
        if (!file || !config.email) {
            alert("Please provide a CSV file and an email address.");
            return;
        }

        setRunning(true);
        setError(null);
        setResult(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('email', config.email);
        formData.append('initial_capital', config.initial_capital);
        formData.append('n_simulations', config.n_simulations);

        try {
            const res = await fetch('http://localhost:8000/api/mcs/simulate', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok && data.status === 'success') {
                setResult(data.metrics);
            } else {
                setError(data.message || "Simulation failed");
            }
        } catch (err) {
            console.error(err);
            setError("Network error or server unavailable.");
        } finally {
            setRunning(false);
        }
    };

    // Prepare chart data if result exists
    const chartData = result ? result.equity_curve_50.map((val, idx) => ({
        index: idx,
        median: val,
        p05: result.equity_curve_05[idx],
        p95: result.equity_curve_95[idx]
    })) : [];

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <TrendingUp className="w-7 h-7 text-accent" />
                    <h1 className="text-2xl font-serif font-semibold text-foreground">Monte Carlo Simulation</h1>
                </div>
                <div className="h-0.5 w-16 bg-accent rounded-full"></div>
            </div>

            {!result && (
                <Card>
                    <CardHeader>
                        <CardTitle>Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <FormSection title="Input Data" icon={TrendingUp}>
                            <div className="space-y-4">
                                <div className="grid w-full max-w-sm items-center gap-2">
                                    <Label htmlFor="file">Trades File (CSV)</Label>
                                    <Input id="file" type="file" onChange={(e) => setFile(e.target.files[0])} accept=".csv" />
                                </div>
                            </div>
                        </FormSection>

                        <FormSection title="Simulation Parameters" icon={TrendingUp}>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label>Initial Capital</Label>
                                    <Input
                                        type="number"
                                        value={config.initial_capital}
                                        onChange={(e) => setConfig({ ...config, initial_capital: parseFloat(e.target.value) })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Simulations</Label>
                                    <Input
                                        type="number"
                                        value={config.n_simulations}
                                        onChange={(e) => setConfig({ ...config, n_simulations: parseInt(e.target.value) })}
                                    />
                                </div>
                                <div className="space-y-2 md:col-span-2">
                                    <Label>Email for Report</Label>
                                    <Input
                                        type="email"
                                        placeholder="user@example.com"
                                        value={config.email}
                                        onChange={(e) => setConfig({ ...config, email: e.target.value })}
                                    />
                                </div>
                            </div>
                        </FormSection>
                    </CardContent>
                    <CardFooter>
                        <Button onClick={handleRunSimulation} disabled={running} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700">
                            {running ? (
                                <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div> Running...</>
                            ) : (
                                <><Play className="w-4 h-4 mr-2" /> Run Simulation</>
                            )}
                        </Button>
                    </CardFooter>
                </Card>
            )}

            {error && (
                <div className="bg-destructive/10 text-destructive border border-destructive/20 p-4 rounded-md mt-4 flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-destructive"></div>
                    {error}
                </div>
            )}

            {result && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom duration-500">
                    {/* Metrics Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Mean Return</CardTitle></CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-green-500">{(result.mean_return * 100).toFixed(2)}%</div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Risk of Ruin</CardTitle></CardHeader>
                            <CardContent>
                                <div className={`text-2xl font-bold ${result.risk_of_ruin > 5 ? 'text-red-500' : 'text-green-500'}`}>
                                    {result.risk_of_ruin.toFixed(2)}%
                                </div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Max Drawdown (95%)</CardTitle></CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-red-500">{result.max_drawdown_95.toFixed(2)}%</div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Chart */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Projected Equity Cone</CardTitle>
                        </CardHeader>
                        <CardContent className="h-[400px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="index" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                    <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1f2937', border: 'none', color: '#f3f4f6' }}
                                        itemStyle={{ color: '#f3f4f6' }}
                                    />
                                    <Legend />
                                    <Line type="monotone" dataKey="p95" name="95th %" stroke="#22c55e" strokeWidth={1} dot={false} strokeDasharray="5 5" />
                                    <Line type="monotone" dataKey="median" name="Median" stroke="#3b82f6" strokeWidth={2} dot={false} />
                                    <Line type="monotone" dataKey="p05" name="5th %" stroke="#ef4444" strokeWidth={1} dot={false} strokeDasharray="5 5" />
                                </LineChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>

                    <div className="flex justify-end">
                        <Button onClick={() => setResult(null)} variant="outline">Run Another Simulation</Button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MCS;
