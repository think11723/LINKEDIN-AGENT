import { motion } from "framer-motion";

export function Spinner() {
  return (
    <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
      <motion.div
        className="h-4 w-4 rounded-full border-2 border-zinc-400 border-t-transparent"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
      />
      Working…
    </div>
  );
}
