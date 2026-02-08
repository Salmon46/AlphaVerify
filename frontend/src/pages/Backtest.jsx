import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Label } from '../components/ui/Label';
import { Upload, Play, CheckCircle, TrendingUp, BarChart2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const Backtest = () => {
    const [files, setFiles] = useState({ data: null, strategy: null });
    const [config, setConfig] = useState({
        email: '',
        cash: 10000.0,
        commission: 0.0,
        class_name: 'StrategyEngine'
    });
    const [running, setRunning] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleFileChange = (e, type) => {
        setFiles(prev => ({ ...prev, [type]: e.target.files[0] }));
    };

    const handleRunBacktest = async () => {
        if (!files.data || !files.strategy) {
            alert("Please provide both Data and Strategy files.");
            return;
        }

        setRunning(true);
        setError(null);
        setResult(null);

        const formData = new FormData();
        formData.append('data', files.data);
        formData.append('strategy', files.strategy);
        formData.append('email', config.email);
        formData.append('cash', config.cash);
        formData.append('commission', config.commission);
        formData.append('class_name', config.class_name);

        try {
            const res = await fetch('http://localhost:8000/api/backtest/run', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok && !data.error) {
                // Normalize result structure (handle wrapped vs raw response)
                const finalResult = data.original_result || data;
                setResult(finalResult);
            } else {
                setError(data.message || data.error || "Backtest failed");
            }
        } catch (err) {
            console.error(err);
            setError("Network error or server unavailable.");
        } finally {
            setRunning(false);
        }
    };

    // Prepare chart data
    const chartData = result?.equity_curve ? result.equity_curve.map((pt) => ({
        time: pt.time.split('T')[0], // Simplify date
        value: pt.value
    })) : [];

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <TrendingUp className="w-7 h-7 text-accent" />
                    <h1 className="text-2xl font-serif font-semibold text-foreground">Strategy Backtest</h1>
                </div>
                <div className="h-0.5 w-16 bg-accent rounded-full"></div>
            </div>

            {!result && (
                <Card>
                    <CardHeader>
                        <CardTitle>Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid w-full max-w-sm items-center gap-1.5">
                            <Label htmlFor="data">Market Data (CSV)</Label>
                            <Input id="data" type="file" onChange={(e) => handleFileChange(e, 'data')} accept=".csv" />
                        </div>
                        <div className="grid w-full max-w-sm items-center gap-1.5">
                            <Label htmlFor="strategy">Strategy File (Python)</Label>
                            <Input id="strategy" type="file" onChange={(e) => handleFileChange(e, 'strategy')} accept=".py" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Initial Cash</Label>
                                <Input
                                    type="number"
                                    value={config.cash}
                                    onChange={(e) => setConfig({ ...config, cash: parseFloat(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Commission (per share/contract)</Label>
                                <Input
                                    type="number"
                                    value={config.commission}
                                    onChange={(e) => setConfig({ ...config, commission: parseFloat(e.target.value) })}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>Strategy Class Name</Label>
                            <Input
                                type="text"
                                value={config.class_name}
                                onChange={(e) => setConfig({ ...config, class_name: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Email for Report</Label>
                            <Input
                                type="email"
                                placeholder="user@example.com"
                                value={config.email}
                                onChange={(e) => setConfig({ ...config, email: e.target.value })}
                            />
                        </div>
                    </CardContent>
                    <CardFooter>
                        <Button onClick={handleRunBacktest} disabled={running} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700">
                            {running ? (
                                <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div> Running...</>
                            ) : (
                                <><Play className="w-4 h-4 mr-2" /> Run Backtest</>
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
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Total Return</CardTitle></CardHeader>
                            <CardContent>
                                <div className={`text-2xl font-bold ${result.metrics?.total_return >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                    {result.metrics?.total_return?.toFixed(2)}%
                                </div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Sharpe Ratio</CardTitle></CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{result.metrics?.sharpe_ratio?.toFixed(3)}</div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Max Drawdown</CardTitle></CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold text-red-500">{result.metrics?.max_drawdown?.toFixed(2)}%</div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Trades</CardTitle></CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{result.trades?.length || 0}</div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Chart */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Equity Curve</CardTitle>
                        </CardHeader>
                        <CardContent className="h-[400px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="time" stroke="#9ca3af" tick={{ fontSize: 12 }} minTickGap={30} />
                                    <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1f2937', border: 'none', color: '#f3f4f6' }}
                                        itemStyle={{ color: '#f3f4f6' }}
                                    />
                                    <Legend />
                                    <Line type="monotone" dataKey="value" name="Portfolio Value" stroke="#3b82f6" strokeWidth={2} dot={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>

                    <div className="flex justify-end">
                        <Button onClick={() => setResult(null)} variant="outline">Run Another Backtest</Button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Backtest;
