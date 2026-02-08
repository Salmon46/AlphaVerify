import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './Card';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

const ToolCard = ({ to, icon: Icon, title, description, colorClass = "text-accent" }) => (
    <Link to={to} className="block group h-full">
        <Card className="h-full transition-all duration-300 hover:shadow-lg hover:-translate-y-1 hover:border-accent/40 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <ArrowRight className="w-5 h-5 text-accent" />
            </div>
            <CardHeader className="pb-3">
                <div className={`w-12 h-12 rounded-lg bg-secondary/50 flex items-center justify-center mb-3 group-hover:bg-accent/10 transition-colors duration-300`}>
                    <Icon className={`w-6 h-6 ${colorClass}`} />
                </div>
                <CardTitle className="group-hover:text-accent transition-colors duration-300">{title}</CardTitle>
            </CardHeader>
            <CardContent>
                <CardDescription className="text-sm leading-relaxed">
                    {description}
                </CardDescription>
            </CardContent>
        </Card>
    </Link>
);

export default ToolCard;
