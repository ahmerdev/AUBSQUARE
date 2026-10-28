import React, { ButtonHTMLAttributes } from 'react';
import { motion, HTMLMotionProps, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'gradient' | 'glass' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  /** Restrained magnetic pull toward the cursor (mouse only). Defaults on for the gradient variant. */
  magnetic?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'gradient',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  onClick,
  magnetic,
  ...props
}) => {
  const reduce = useReducedMotion();
  const canMagnet = (magnetic ?? variant === 'gradient') && !reduce;
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 240, damping: 18, mass: 0.45 });
  const sy = useSpring(y, { stiffness: 240, damping: 18, mass: 0.45 });

  const baseStyles =
    'group relative inline-flex items-center justify-center font-medium rounded-full transition-[background,box-shadow,border-color,color,opacity] duration-300 select-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px] overflow-hidden';

  const sizeStyles = {
    sm: 'text-xs px-4 py-2 gap-1.5',
    md: 'text-sm px-6 py-2.5 gap-2',
    lg: 'text-base px-6 sm:px-8 py-3.5 gap-2.5 font-semibold',
  };

  const variantStyles = {
    gradient: 'bg-aub-gradient text-white shadow-glow-magenta hover:shadow-glow-purple border border-white/20',
    glass: 'glass-panel text-white hover:bg-white/10 hover:border-aub-purple/50',
    outline: 'border border-aub-border hover:border-aub-magenta text-aub-text-primary hover:text-white hover:bg-white/5',
    ghost: 'text-aub-text-secondary hover:text-white hover:bg-white/5',
  };

  const { onPointerMove, onPointerLeave, ...rest } = props as HTMLMotionProps<'button'>;

  return (
    <motion.button
      style={canMagnet ? { x: sx, y: sy } : undefined}
      whileHover={reduce || disabled ? undefined : { scale: 1.03 }}
      whileTap={reduce || disabled ? undefined : { scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 380, damping: 24 }}
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isLoading}
      onClick={onClick}
      onPointerMove={(e) => {
        if (canMagnet && e.pointerType === 'mouse') {
          const r = e.currentTarget.getBoundingClientRect();
          x.set((e.clientX - r.left - r.width / 2) * 0.2);
          y.set((e.clientY - r.top - r.height / 2) * 0.28);
        }
        onPointerMove?.(e);
      }}
      onPointerLeave={(e) => {
        x.set(0);
        y.set(0);
        onPointerLeave?.(e);
      }}
      {...rest}
    >
      {variant === 'gradient' && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -translate-x-full transition-transform duration-1000 ease-out [@media(hover:hover)]:group-hover:translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent"
        />
      )}
      {isLoading ? (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" aria-hidden="true">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      ) : (
        leftIcon && <span className="inline-flex shrink-0">{leftIcon}</span>
      )}
      <span className="relative">{children}</span>
      {!isLoading && rightIcon && <span className="relative inline-flex shrink-0">{rightIcon}</span>}
    </motion.button>
  );
};
