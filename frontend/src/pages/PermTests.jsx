import React, { useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Label } from '../components/ui/Label';
import { Upload, Play, CheckCircle, Shuffle, AlertTriangle } from 'lucide-react';
import FormSection from '../components/ui/FormSection';

const PermTests = () => {
    const [step, setStep] = useState(1);
    const [files, setFiles] = useState({ data: null, strategy: null });
    const [config, setConfig] = useState({
        email: '',
        initial_cash: 100000,
        n_permutations: 1000,
        metric: 'sharpe', // sharpe or profit_factor
        data_filename: '',
        strategy_filename: ''
    });
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('');
    const [logs, setLogs] = useState([]);
    const [result, setResult] = useState(null);
    const wsRef = useRef(null);

    const handleFileChange = (e, type) => {
        setFiles(prev => ({ ...prev, [type]: e.target.files[0] }));
    };

    const handleUpload = async () => {
        if (!files.data || !files.strategy) {
            alert("Please select both Data and Strategy files.");
            return;
        }

        setUploading(true);
        const formData = new FormData();
        formData.append('data_file', files.data);
        formData.append('strategy_file', files.strategy);

        try {
            const res = await fetch('http://localhost:8000/api/perm-tests/upload-files', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.data_filename) {
                setConfig(prev => ({
                    ...prev,
                    data_filename: data.data_filename,
                    strategy_filename: data.strategy_filename
                }));
                setStep(2);
            } else {
                alert("Upload failed.");
            }
        } catch (err) {
            console.error(err);
            alert("Upload error.");
        } finally {
            setUploading(false);
        }
    };

    const handleRunTest = () => {
        if (!config.email) {
            alert("Please enter an email address.");
            return;
        }

        setStep(3);
        setLogs([]);
        setProgress(0);
        setStatus('Initializing...');

        // Connect WebSocket
        wsRef.current = new WebSocket('ws://localhost:8000/api/perm-tests/ws/run-permutation-test');

        wsRef.current.onopen = () => {
            console.log("Connected to PermTests WebSocket");
            wsRef.current.send(JSON.stringify(config));
        };

        wsRef.current.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'progress') {
                if (msg.status) setStatus(msg.status);
                if (msg.completed !== undefined) {
                    const pct = (msg.completed / msg.total) * 100;
                    setProgress(pct);
                    setStatus(`Permuting... ${msg.completed}/${msg.total}`);
                }
            } else if (msg.type === 'result') {
                setResult(msg.data);
                setStatus('Test Complete!');
                setProgress(100);
                setStep(4);
            } else if (msg.type === 'error') {
                setStatus(`Error: ${msg.message}`);
                setLogs(prev => [...prev, `[ERROR] ${msg.message}`]);
            }
        };

        wsRef.current.onerror = (err) => {
            console.error("WebSocket error", err);
            setStatus("Connection error");
        };
    };

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <Shuffle className="w-7 h-7 text-accent" />
                    <h1 className="text-2xl font-serif font-semibold text-foreground">Permutation Tests</h1>
                </div>
                <div className="h-0.5 w-16 bg-accent rounded-full"></div>
            </div>

            {/* Step 1: Upload */}
            {step === 1 && (
                <Card>
                    <CardHeader>
                        <CardTitle>1. Upload Files</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <FormSection title="Data Source" icon={Shuffle}>
                            <div className="space-y-4">
                                <div className="grid w-full max-w-sm items-center gap-2">
                                    <Label htmlFor="data">Market Data (CSV)</Label>
                                    <Input id="data" type="file" onChange={(e) => handleFileChange(e, 'data')} accept=".csv" />
                                </div>
                                <div className="grid w-full max-w-sm items-center gap-2">
                                    <Label htmlFor="strategy">Strategy File (Python)</Label>
                                    <Input id="strategy" type="file" onChange={(e) => handleFileChange(e, 'strategy')} accept=".py" />
                                </div>
                            </div>
                        </FormSection>
                    </CardContent>
                    <CardFooter>
                        <Button onClick={handleUpload} disabled={uploading}>
                            {uploading ? 'Uploading...' : 'Next: Configure'}
                        </Button>
                    </CardFooter>
                </Card>
            )}

            {/* Step 2: Configure */}
            {step === 2 && (
                <Card>
                    <CardHeader>
                        <CardTitle>2. Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <FormSection title="Simulation Settings" icon={Shuffle}>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label>Initial Capital</Label>
                                    <Input
                                        type="number"
                                        value={config.initial_cash}
                                        onChange={(e) => setConfig({ ...config, initial_cash: parseFloat(e.target.value) })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Permutations</Label>
                                    <Input
                                        type="number"
                                        value={config.n_permutations}
                                        onChange={(e) => setConfig({ ...config, n_permutations: parseInt(e.target.value) })}
                                    />
                                </div>
                            </div>
                        </FormSection>

                        <FormSection title="Analysis Metrics" icon={Shuffle}>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label>Metric</Label>
                                    <select
                                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        value={config.metric}
                                        onChange={(e) => setConfig({ ...config, metric: e.target.value })}
                                    >
                                        <option value="sharpe">Sharpe Ratio</option>
                                        <option value="profit_factor">Profit Factor</option>
                                    </select>
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
                            </div>
                        </FormSection>
                    </CardContent>
                    <CardFooter className="flex gap-2">
                        <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
                        <Button onClick={handleRunTest} className="gap-2">
                            <Play className="w-4 h-4" /> Run Test
                        </Button>
                    </CardFooter>
                </Card>
            )}

            {/* Step 3: Running / Result */}
            {(step === 3 || step === 4) && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            {step === 4 ? <CheckCircle className="text-green-600" /> : <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>}
                            {status}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Progress Bar */}
                        <div className="w-full bg-secondary h-2.5 rounded-full dark:bg-gray-700">
                            <div
                                className="bg-primary h-2.5 rounded-full transition-all duration-300"
                                style={{ width: `${progress}%` }}
                            ></div>
                        </div>
                        <p className="text-right text-sm text-muted-foreground">{progress.toFixed(0)}%</p>

                        {/* Logs */}
                        <div className="bg-card border text-muted-foreground font-mono text-xs p-4 rounded-md h-32 overflow-y-auto">
                            {logs.map((log, i) => (
                                <div key={i}>{log}</div>
                            ))}
                        </div>

                        {/* Result Display */}
                        {result && (
                            <div className="space-y-6 animate-in fade-in zoom-in duration-300">
                                <div className={`p-6 rounded-lg border text-center ${result.is_significant ? 'bg-green-500/10 border-green-500/50' : 'bg-red-500/10 border-red-500/50'}`}>
                                    <h3 className="text-xl font-bold mb-2">
                                        {result.is_significant ? "✅ Strategy is Significant" : "❌ Strategy is Not Significant"}
                                    </h3>
                                    <div className="flex justify-center items-baseline gap-2">
                                        <span className="text-muted-foreground">p-value:</span>
                                        <span className="text-3xl font-bold">{result.p_value.toFixed(4)}</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground mt-2">
                                        (Lower is better, typically &lt; 0.05)
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-card border p-4 rounded-lg">
                                        <div className="text-sm text-muted-foreground">Original Score</div>
                                        <div className="text-2xl font-bold text-blue-500">{result.original_score.toFixed(4)}</div>
                                    </div>
                                    <div className="bg-card border p-4 rounded-lg">
                                        <div className="text-sm text-muted-foreground">Permuted Mean</div>
                                        <div className="text-2xl font-bold text-gray-500">{result.permuted_mean.toFixed(4)}</div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </CardContent>
                    <CardFooter>
                        {step === 4 && (
                            <Button onClick={() => setStep(1)} variant="outline">Start New Test</Button>
                        )}
                    </CardFooter>
                </Card>
            )}
        </div>
    );
};

export default PermTests;
