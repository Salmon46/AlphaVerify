import React, { useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Label } from '../components/ui/Label';
import { Upload, Play, CheckCircle, Activity, BarChart2 } from 'lucide-react';
import FormSection from '../components/ui/FormSection';

const Sensitivity = () => {
    const [step, setStep] = useState(1);
    const [files, setFiles] = useState({ data: null, strategy: null });
    const [config, setConfig] = useState({
        email: '',
        initial_cash: 10000,
        mode: 'grid', // grid or random
        iterations: 100, // for random
        data_filename: '',
        strategy_filename: '',
        parameters: {}
    });
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('');
    const [logs, setLogs] = useState([]);
    const [result, setResult] = useState(null);
    const [detectedParams, setDetectedParams] = useState({});
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
            const res = await fetch('http://localhost:8000/api/sensitivity/upload-files', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.status === 'success') {
                setConfig(prev => ({
                    ...prev,
                    data_filename: data.data_filename,
                    strategy_filename: data.strategy_filename,
                    // Initialize empty ranges for detected params
                    parameters: Object.keys(data.detected_parameters || {}).reduce((acc, key) => {
                        acc[key] = { min: 10, max: 100, step: 10 }; // Default defaults
                        return acc;
                    }, {})
                }));
                setDetectedParams(data.detected_parameters || {});
                setStep(2);
            } else {
                alert(`Upload failed: ${data.message}`);
            }
        } catch (err) {
            console.error(err);
            alert("Upload error.");
        } finally {
            setUploading(false);
        }
    };

    const handleRunAnalysis = () => {
        if (!config.email) {
            alert("Please enter an email address.");
            return;
        }

        setStep(3);
        setLogs([]);
        setProgress(0);
        setStatus('Initializing...');

        // Connect WebSocket
        wsRef.current = new WebSocket('ws://localhost:8000/api/sensitivity/ws/run-sensitivity');

        wsRef.current.onopen = () => {
            console.log("Connected to Sensitivity WebSocket");
            wsRef.current.send(JSON.stringify(config));
        };

        wsRef.current.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'progress') {
                setStatus(msg.message);
                if (msg.progress !== undefined) setProgress(msg.progress);
                setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg.message}`]);
            } else if (msg.type === 'result') {
                setResult(msg.data);
                setStatus('Analysis Complete!');
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
                    <Activity className="w-7 h-7 text-accent" />
                    <h1 className="text-2xl font-serif font-semibold text-foreground">Sensitivity Analysis</h1>
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
                        <FormSection title="Data Source" icon={Activity}>
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
                        <FormSection title="Analysis Settings" icon={Activity}>
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
                                    <Label>Email for Report</Label>
                                    <Input
                                        type="email"
                                        placeholder="user@example.com"
                                        value={config.email}
                                        onChange={(e) => setConfig({ ...config, email: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Mode</Label>
                                    <select
                                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        value={config.mode}
                                        onChange={(e) => setConfig({ ...config, mode: e.target.value })}
                                    >
                                        <option value="grid">Grid Search</option>
                                        <option value="random">Random Search</option>
                                    </select>
                                </div>
                                {config.mode === 'random' && (
                                    <div className="space-y-2">
                                        <Label>Iterations</Label>
                                        <Input
                                            type="number"
                                            value={config.iterations}
                                            onChange={(e) => setConfig({ ...config, iterations: parseInt(e.target.value) })}
                                        />
                                    </div>
                                )}
                            </div>
                        </FormSection>

                        <FormSection title="Parameter Ranges" icon={Activity}>
                            <div className="bg-muted/30 p-4 rounded-md space-y-4 border">
                                {Object.keys(detectedParams).length === 0 ? (
                                    <p className="text-sm text-muted-foreground text-center py-4">No parameters detected.</p>
                                ) : (
                                    Object.keys(detectedParams).map((paramName) => (
                                        <div key={paramName} className="border-b pb-6 last:border-0 last:pb-0 border-border/50">
                                            <Label className="text-accent font-medium mb-3 block text-base">{paramName}</Label>
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                                <div>
                                                    <span className="text-xs text-muted-foreground mb-1 block">Min</span>
                                                    <Input
                                                        type="number"
                                                        value={config.parameters[paramName]?.min || 0}
                                                        onChange={(e) => {
                                                            const newParams = { ...config.parameters };
                                                            if (!newParams[paramName]) newParams[paramName] = {};
                                                            newParams[paramName].min = parseFloat(e.target.value);
                                                            setConfig({ ...config, parameters: newParams });
                                                        }}
                                                    />
                                                </div>
                                                <div>
                                                    <span className="text-xs text-muted-foreground mb-1 block">Max</span>
                                                    <Input
                                                        type="number"
                                                        value={config.parameters[paramName]?.max || 100}
                                                        onChange={(e) => {
                                                            const newParams = { ...config.parameters };
                                                            if (!newParams[paramName]) newParams[paramName] = {};
                                                            newParams[paramName].max = parseFloat(e.target.value);
                                                            setConfig({ ...config, parameters: newParams });
                                                        }}
                                                    />
                                                </div>

                                                {/* Grid Search: Step */}
                                                {config.mode === 'grid' && (
                                                    <div>
                                                        <span className="text-xs text-muted-foreground mb-1 block">Step</span>
                                                        <Input
                                                            type="number"
                                                            value={config.parameters[paramName]?.step || 10}
                                                            onChange={(e) => {
                                                                const newParams = { ...config.parameters };
                                                                if (!newParams[paramName]) newParams[paramName] = {};
                                                                newParams[paramName].step = parseFloat(e.target.value);
                                                                setConfig({ ...config, parameters: newParams });
                                                            }}
                                                        />
                                                    </div>
                                                )}

                                                {/* Random Search: Distribution & Sigma */}
                                                {config.mode === 'random' && (
                                                    <>
                                                        <div>
                                                            <span className="text-xs text-muted-foreground mb-1 block">Dist</span>
                                                            <select
                                                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                                                value={config.parameters[paramName]?.distribution || 'uniform'}
                                                                onChange={(e) => {
                                                                    const newParams = { ...config.parameters };
                                                                    if (!newParams[paramName]) newParams[paramName] = {};
                                                                    newParams[paramName].distribution = e.target.value;
                                                                    setConfig({ ...config, parameters: newParams });
                                                                }}
                                                            >
                                                                <option value="uniform">Uniform</option>
                                                                <option value="normal">Normal</option>
                                                            </select>
                                                        </div>
                                                        {config.parameters[paramName]?.distribution === 'normal' && (
                                                            <div>
                                                                <span className="text-xs text-muted-foreground mb-1 block">Sigma</span>
                                                                <Input
                                                                    type="number"
                                                                    placeholder="Auto"
                                                                    value={config.parameters[paramName]?.sigma || ''}
                                                                    onChange={(e) => {
                                                                        const newParams = { ...config.parameters };
                                                                        if (!newParams[paramName]) newParams[paramName] = {};
                                                                        newParams[paramName].sigma = parseFloat(e.target.value);
                                                                        setConfig({ ...config, parameters: newParams });
                                                                    }}
                                                                />
                                                            </div>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </FormSection>
                    </CardContent>
                    <CardFooter className="flex gap-2">
                        <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
                        <Button onClick={handleRunAnalysis} className="gap-2">
                            <Play className="w-4 h-4" /> Run Analysis
                        </Button>
                    </CardFooter>
                </Card>
            )}

            {/* Step 3: Running / Result */}
            {(step === 3 || step === 4) && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            {step === 4 ? <CheckCircle className="text-green-500" /> : <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-orange-500"></div>}
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
                        <div className="bg-card border text-muted-foreground font-mono text-xs p-4 rounded-md h-64 overflow-y-auto">
                            {logs.map((log, i) => (
                                <div key={i}>{log}</div>
                            ))}
                        </div>

                        {/* Result Display */}
                        {result && (
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-card border p-4 rounded-lg">
                                        <div className="text-sm text-muted-foreground">Best Sharpe Ratio</div>
                                        <div className="text-2xl font-bold text-green-500">{result.best?.metrics?.sharpe?.toFixed(4)}</div>
                                        <div className="text-xs text-muted-foreground mt-1">
                                            Params: {JSON.stringify(result.best?.params)}
                                        </div>
                                    </div>
                                    <div className="bg-card border p-4 rounded-lg">
                                        <div className="text-sm text-muted-foreground">Total Runs</div>
                                        <div className="text-2xl font-bold">{result.total_runs}</div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </CardContent>
                    <CardFooter>
                        {step === 4 && (
                            <Button onClick={() => setStep(1)} variant="outline">Start New Analysis</Button>
                        )}
                    </CardFooter>
                </Card>
            )}
        </div>
    );
};

export default Sensitivity;
