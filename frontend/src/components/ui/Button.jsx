import React from 'react';

const Button = React.forwardRef(({ className, variant = "default", size = "default", ...props }, ref) => {
    const variants = {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90 hover:shadow-md",
        destructive: "bg-destructive text-destructive-foreground shadow hover:bg-destructive/90 hover:shadow-md",
        outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground hover:shadow",
        secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 hover:shadow",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        gold: "bg-accent text-accent-foreground shadow hover:opacity-90 hover:shadow-md",
    };

    const sizes = {
        default: "h-10 px-5 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-md px-8 text-base",
        icon: "h-10 w-10",
    };

    return (
        <button
            className={`inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
            ref={ref}
            {...props}
        />
    );
});

Button.displayName = "Button";

export { Button };
