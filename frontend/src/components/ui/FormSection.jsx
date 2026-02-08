import React from 'react';

const FormSection = ({ title, icon: Icon, children, className = "" }) => {
    return (
        <div className={`mb-8 border rounded-lg overflow-hidden bg-card/50 ${className}`}>
            <div className="bg-secondary/30 px-6 py-4 border-b flex items-center gap-3">
                {Icon && <Icon className="w-5 h-5 text-accent" />}
                <h3 className="font-serif font-medium text-lg text-foreground tracking-wide">
                    {title}
                </h3>
            </div>
            <div className="p-6 space-y-6">
                {children}
            </div>
        </div>
    );
};

export default FormSection;
