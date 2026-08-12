import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[120px] w-full rounded-xl border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-zinc-200 dark:border-zinc-700 dark:focus:border-zinc-200 dark:focus:ring-zinc-800",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
