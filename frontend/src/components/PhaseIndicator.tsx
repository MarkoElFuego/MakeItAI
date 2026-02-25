const PHASE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  SCOUT: { label: "Scout", color: "bg-blue-500", icon: "🔍" },
  CRAFTER: { label: "Crafter", color: "bg-orange-600", icon: "📐" },
  MASTER: { label: "Master", color: "bg-emerald-600", icon: "📚" },
  TROUBLESHOOTER: { label: "Troubleshooter", color: "bg-amber-500", icon: "🔧" },
  MERCHANT: { label: "Merchant", color: "bg-purple-600", icon: "🏪" },
};

export default function PhaseIndicator({ phase }: { phase: string }) {
  const config = PHASE_CONFIG[phase] || PHASE_CONFIG.MASTER;

  return (
    <div className="flex items-center gap-2">
      <span className="text-lg">{config.icon}</span>
      <span
        className={`${config.color} text-white text-xs font-semibold px-3 py-1 rounded-full`}
      >
        {config.label}
      </span>
    </div>
  );
}
