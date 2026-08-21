/**
 * RiskScoreBadge — Color-coded risk score indicator.
 * Green (0-30), Yellow (31-70), Red (71-100)
 */

import PropTypes from "prop-types";

export default function RiskScoreBadge({ score, label }) {
  const getColor = () => {
    if (score <= 30) return { bg: "bg-emerald-500/20", text: "text-emerald-400", border: "border-emerald-500/30", glow: "shadow-emerald-500/20" };
    if (score <= 70) return { bg: "bg-amber-500/20", text: "text-amber-400", border: "border-amber-500/30", glow: "shadow-amber-500/20" };
    return { bg: "bg-red-500/20", text: "text-red-400", border: "border-red-500/30", glow: "shadow-red-500/20" };
  };

  const getIcon = () => {
    if (score <= 30) return "✓";
    if (score <= 70) return "⚠";
    return "✕";
  };

  const colors = getColor();

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${colors.bg} ${colors.border} ${colors.text} shadow-lg ${colors.glow}`}>
      <span className="text-sm font-bold">{getIcon()}</span>
      <span className="text-sm font-semibold">{score}%</span>
      <span className="text-xs uppercase tracking-wider opacity-80">{label}</span>
    </div>
  );
}

RiskScoreBadge.propTypes = {
  score: PropTypes.number.isRequired,
  label: PropTypes.string.isRequired,
};
