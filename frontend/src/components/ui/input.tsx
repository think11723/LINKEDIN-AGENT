import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-xl border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-200 dark:border-zinc-700 dark:focus:border-zinc-200 dark:focus:ring-zinc-800",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
