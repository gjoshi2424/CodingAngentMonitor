import { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  className?: string;
}

const baseClassName =
  "px-5 py-2.5 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer";

export default function Button({ children, className = "", type = "button", ...props }: ButtonProps) {
  const mergedClassName = className ? `${baseClassName} ${className}` : baseClassName;

  return (
    <button type={type} className={mergedClassName} {...props}>
      {children}
    </button>
  );
}